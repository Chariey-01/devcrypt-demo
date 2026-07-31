import { forwardRef, useImperativeHandle, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type * as monacoTypes from "monaco-editor";
import { Icon } from "../icons";
import { draftStore } from "../hooks/useLocalDraft";

export interface MonacoCodeEditorHandle {
  getValue(): string;
}

const KNOWN_LANGUAGES = [
  "python", "javascript", "typescript", "java", "csharp", "cpp", "c", "go", "ruby", "rust",
  "php", "swift", "kotlin", "sql", "shell",
];

function monacoLanguageFor(lang: string | null | undefined): string {
  const normalized = (lang || "python").toLowerCase();
  return KNOWN_LANGUAGES.includes(normalized) ? normalized : "plaintext";
}

// Ported from app/static/app.js's mountCodeEditor(). Deliberately uncontrolled: `defaultValue`
// is only read once per mount (this component is keyed by mission id in ChallengePanel, so a
// mission change remounts it with a fresh defaultValue -- same "dispose and recreate" behavior
// as the vanilla version's monacoEditorMissionId check). The parent reads the live value
// on-demand (Run Tests / Submit) via the exposed getValue(), never by re-passing a `value` prop
// -- that would fight Monaco's own cursor/undo-history state on every poll tick.
export const MonacoCodeEditor = forwardRef<
  MonacoCodeEditorHandle,
  { missionId: number; teamName: string | null; language: string | null | undefined; startValue: string }
>(function MonacoCodeEditor({ missionId, teamName, language, startValue }, ref) {
  const editorRef = useRef<monacoTypes.editor.IStandaloneCodeEditor | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useImperativeHandle(ref, () => ({
    getValue: () => editorRef.current?.getValue() ?? "",
  }));

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
    editor.onDidChangeModelContent(() => {
      const value = editor.getValue();
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      // Debounced (not per-keystroke) -- Monaco's own auto-close-bracket/-quote insertions can
      // fire several content-change events per keypress; fidelity to the exact keystroke
      // doesn't matter, only that it's saved shortly after the player pauses.
      saveTimerRef.current = setTimeout(() => draftStore.save(teamName, missionId, value), 400);
    });
    // Auto-focusing means the poll loop's next tick naturally leaves this alone (React only
    // remounts this component on a mission change, never on a plain poll re-render), matching
    // the vanilla version's intent of not fighting an actively-focused editor.
    editor.focus();
  };

  return (
    <div id="code-editor-mount" className="monaco-mount">
      <Editor
        height="320px"
        defaultLanguage={monacoLanguageFor(language)}
        defaultValue={startValue}
        theme="vs-dark"
        onMount={handleMount}
        loading={
          <p className="narrative-message">
            <Icon name="terminal" size={13} /> Loading code editor…
          </p>
        }
        options={{
          automaticLayout: true,
          minimap: { enabled: false },
          fontSize: 14,
          tabSize: 4,
          insertSpaces: true,
          autoClosingBrackets: "always",
          autoClosingQuotes: "always",
          scrollBeyondLastLine: false,
          wordWrap: "on",
        }}
      />
    </div>
  );
});
