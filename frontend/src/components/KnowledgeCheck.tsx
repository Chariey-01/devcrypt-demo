import { useState } from "react";
import { Icon } from "../icons";
import { api } from "../api";
import type { KnowledgeAnswerResponse, KnowledgeQuestion } from "../types";

const LETTERS = ["A", "B", "C", "D", "E", "F"];

// Ported from app/static/app.js's Knowledge Check block in renderMissionPanel() +
// attachKnowledgeCheckHandlers(). Select, then explicitly confirm -- two clicks, not one. The
// POST only ever fires from the confirm click, never from selecting a card.
export function KnowledgeCheck({
  questions,
  onAnswered,
  showMessage,
}: {
  questions: KnowledgeQuestion[];
  onAnswered: () => void;
  showMessage: (text: string) => void;
}) {
  const [selected, setSelected] = useState<{ questionId: number; optionId: number } | null>(null);
  const [resultClass, setResultClass] = useState<"correct" | "incorrect" | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const total = questions.length;
  const answeredCount = questions.filter((q) => q.answered).length;
  const nextQuestion = questions.find((q) => !q.answered);

  async function confirm() {
    if (!selected) return;
    setSubmitting(true);
    const res = await api<KnowledgeAnswerResponse>(`/missions/knowledge-check/${selected.questionId}/answer`, {
      method: "POST",
      body: JSON.stringify({ option_id: selected.optionId }),
    });
    setResultClass(res.ok && res.data.correct ? "correct" : "incorrect");
    showMessage(res.data.message || res.data.error || "");
    setSubmitting(false);
    onAnswered();
  }

  return (
    <div className="kc-block">
      <div className="kc-head">
        <p className="section-heading">
          <Icon name="radar" size={14} /> Stage 1 — Knowledge Check
        </p>
        <span className="kc-counter">
          Question {Math.min(answeredCount + 1, total)} of {total}
        </span>
      </div>
      <div className="kc-dots">
        {questions.map((q, i) => (
          <span
            key={q.id}
            className={`kc-dot ${q.answered ? "done" : i === answeredCount ? "current" : ""}`}
          />
        ))}
      </div>
      <p className="hint-text">
        General discipline knowledge — answer every question to unlock this booth's coding
        challenge. Correct answers reveal a cipher clue.
      </p>
      {nextQuestion && (
        <>
          <p className="kc-question">{nextQuestion.question_text}</p>
          <div className="kc-options">
            {nextQuestion.options.map((o, i) => {
              const isSelected = selected?.questionId === nextQuestion.id && selected.optionId === o.id;
              const cls = isSelected && resultClass ? resultClass : isSelected ? "selected" : "";
              return (
                <button
                  key={o.id}
                  type="button"
                  className={`kc-option ${cls}`.trim()}
                  disabled={submitting}
                  onClick={() => {
                    setResultClass(null);
                    setSelected({ questionId: nextQuestion.id, optionId: o.id });
                  }}
                >
                  <span className="kc-option-letter">{LETTERS[i] || String(i + 1)}</span>
                  <span className="kc-option-text">{o.option_text}</span>
                </button>
              );
            })}
          </div>
          <div className={`kc-confirm-row${selected?.questionId === nextQuestion.id ? "" : " hidden"}`}>
            <button type="button" disabled={submitting || !selected} onClick={confirm}>
              <Icon name="check" size={13} /> Confirm Answer
            </button>
          </div>
        </>
      )}
    </div>
  );
}
