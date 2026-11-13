"""LangGraph workflow for IELTS essay grading.

Nodes:
  1. validate_input  — check essay text and email (guardrails)
  2. retrieve_rubric — fetch relevant rubric chunks from RAG (4 calls, 1 per criterion)
  3. grade           — call LLM to grade the essay
  4. validate_output — check output schema and evidence, retry if evidence missing

No checkpointer. 'Waiting for examiner' is handled via status column in DB.
"""

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ielts_ai.config import get_settings
from ielts_ai.db.repo import save_ai_result, set_status
from ielts_ai.guardrails.input_checks import validate_input
from ielts_ai.guardrails.output_checks import check_evidence, validate_output
from ielts_ai.llm.client import get_llm_client
from ielts_ai.observability.call_logger import log_call
from ielts_ai.rag.retriever import RubricIndexNotFoundError, search_rubric
from ielts_ai.schemas import Criterion, EssayStatus, GradingResult

logger = logging.getLogger(__name__)


class GradingState(TypedDict):
    """State passed between LangGraph nodes."""

    essay_id: int
    prompt_text: str
    essay_text: str
    candidate_email: str
    version: int
    rubric_chunks: list
    result: GradingResult | None
    errors: list[str]
    warnings: list[str]


def _validate_input_node(state: GradingState) -> GradingState:
    """Node 1: Validate input essay and email.

    Input errors leave the essay status unchanged (pending) and are returned to the caller.
    """
    logger.info("Node: validate_input (essay_id=%s)", state["essay_id"])
    check = validate_input(state["essay_text"], state["candidate_email"])

    errors = list(state.get("errors", []))
    warnings = list(state.get("warnings", []))

    errors.extend(check.errors)
    warnings.extend(check.warnings)

    return {**state, "errors": errors, "warnings": warnings}


def _retrieve_rubric_node(state: GradingState) -> GradingState:
    """Node 2: Retrieve relevant rubric chunks from RAG.

    Executes 4 calls to search_rubric (one per criterion: TR, CC, LR, GRA),
    logging each call with step 'retrieve'.
    """
    logger.info("Node: retrieve_rubric (essay_id=%s)", state["essay_id"])
    settings = get_settings()
    chunks = []
    errors = list(state.get("errors", []))

    # Slice essay to create a focused semantic query for each criterion
    essay_slice = state["essay_text"][:300].strip()

    try:
        for criterion in Criterion:
            query = f"{criterion.name} {essay_slice}"
            with log_call("retrieve", essay_id=state["essay_id"], db_path=settings.db_path) as ctx:
                retrieved = search_rubric(criterion, query, top_k=3)
                ctx.set_tokens(
                    len(query.split()),
                    sum(len(c.text.split()) for c in retrieved),
                )
            chunks.extend(retrieved)
    except RubricIndexNotFoundError as err:
        logger.error("Rubric retrieval failed: %s", err)
        errors.append(str(err))
        try:
            set_status(settings.db_path, state["essay_id"], EssayStatus.grading_failed.value)
        except Exception:
            pass
        return {**state, "rubric_chunks": [], "errors": errors}
    except Exception as exc:
        logger.error("Unexpected error during retrieval: %s", exc)
        errors.append(f"Rubric retrieval failed: {exc}")
        try:
            set_status(settings.db_path, state["essay_id"], EssayStatus.grading_failed.value)
        except Exception:
            pass
        return {**state, "rubric_chunks": [], "errors": errors}

    logger.debug("Retrieved %d rubric chunks for essay %s", len(chunks), state["essay_id"])
    return {**state, "rubric_chunks": chunks, "errors": errors}


def _grade_node(state: GradingState) -> GradingState:
    """Node 3: Grade the essay using LLM."""
    if state.get("errors"):
        return state

    logger.info("Node: grade (essay_id=%s)", state["essay_id"])
    settings = get_settings()
    llm_client = get_llm_client()

    try:
        from ielts_ai.agent.evaluate import evaluate_essay

        result = evaluate_essay(
            essay_id=state["essay_id"],
            prompt_text=state["prompt_text"],
            essay_text=state["essay_text"],
            rubric_chunks=state["rubric_chunks"],
            llm_client=llm_client,
            warnings=state.get("warnings", []),
            version=state.get("version", 1),
        )
        return {**state, "result": result}
    except Exception as exc:
        logger.error("Grading failed for essay %s: %s", state["essay_id"], exc)
        try:
            set_status(settings.db_path, state["essay_id"], EssayStatus.grading_failed.value)
        except Exception:
            pass
        return {**state, "errors": state.get("errors", []) + [str(exc)]}


def _validate_output_node(state: GradingState) -> GradingState:
    """Node 4: Validate output schema and evidence.

    If any evidence is missing from the essay, retry grading once.
    If still invalid after retry, keep the result and append warnings.
    """
    if state.get("errors") or state.get("result") is None:
        return state

    logger.info("Node: validate_output (essay_id=%s)", state["essay_id"])
    settings = get_settings()
    result = state["result"]
    essay_text = state["essay_text"]

    evidence_warnings = check_evidence(result, essay_text)

    # If evidence is missing, retry grading once
    if evidence_warnings:
        logger.warning(
            "Evidence quotes missing in first attempt for essay %s. Retrying grade node once.",
            state["essay_id"],
        )
        try:
            from ielts_ai.agent.evaluate import evaluate_essay

            retry_warning = [
                "CRITICAL: The previous quotes were not found verbatim in the essay. "
                "You MUST copy exact character sequences from the candidate's essay."
            ]
            retry_result = evaluate_essay(
                essay_id=state["essay_id"],
                prompt_text=state["prompt_text"],
                essay_text=state["essay_text"],
                rubric_chunks=state["rubric_chunks"],
                llm_client=get_llm_client(),
                warnings=state.get("warnings", []) + retry_warning,
                version=state.get("version", 1),
            )
            result = retry_result
        except Exception as retry_exc:
            logger.warning(
                "Retry on missing evidence failed: %s; keeping original result.", retry_exc
            )

    # Re-validate output and collect all warnings
    all_output_warnings = validate_output(result, essay_text)
    for w in all_output_warnings:
        if w not in result.warnings:
            result.warnings.append(w)

    # Save ai_results version 1 and update status to ai_done
    try:
        save_ai_result(
            db_path=settings.db_path,
            essay_id=state["essay_id"],
            version=state.get("version", 1),
            result_json=result.model_dump_json(),
        )
        set_status(settings.db_path, state["essay_id"], EssayStatus.ai_done.value)
    except Exception as exc:
        logger.error("Could not persist result / update status to ai_done: %s", exc)
        return {**state, "errors": state.get("errors", []) + [str(exc)]}

    return {**state, "result": result}


def _has_errors(state: GradingState) -> str:
    """Conditional edge: route to END if there are input errors or retrieval errors."""
    if state.get("errors"):
        return "error"
    return "continue"


def build_graph() -> Any:
    """Build and compile the LangGraph grading workflow."""
    workflow = StateGraph(GradingState)

    workflow.add_node("validate_input", _validate_input_node)
    workflow.add_node("retrieve_rubric", _retrieve_rubric_node)
    workflow.add_node("grade", _grade_node)
    workflow.add_node("validate_output", _validate_output_node)

    workflow.set_entry_point("validate_input")

    # Conditional edge: input errors terminate immediately without grading
    workflow.add_conditional_edges(
        "validate_input",
        _has_errors,
        {"error": END, "continue": "retrieve_rubric"},
    )
    workflow.add_conditional_edges(
        "retrieve_rubric",
        _has_errors,
        {"error": END, "continue": "grade"},
    )
    workflow.add_edge("grade", "validate_output")
    workflow.add_edge("validate_output", END)

    return workflow.compile()


_graph: Any = None


def run_grading(
    essay_id: int,
    prompt_text: str,
    essay_text: str,
    candidate_email: str,
    version: int = 1,
) -> GradingState:
    """Entry point: run the full grading workflow for an essay."""
    global _graph
    if _graph is None:
        _graph = build_graph()

    initial_state: GradingState = {
        "essay_id": essay_id,
        "prompt_text": prompt_text,
        "essay_text": essay_text,
        "candidate_email": candidate_email,
        "version": version,
        "rubric_chunks": [],
        "result": None,
        "errors": [],
        "warnings": [],
    }

    logger.info("Starting grading workflow for essay %s", essay_id)
    final_state = _graph.invoke(initial_state)
    return final_state
