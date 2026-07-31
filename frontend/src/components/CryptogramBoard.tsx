import { Icon } from "../icons";
import type { CryptogramWord } from "../types";

export function CryptogramBoard({ board }: { board: CryptogramWord[] }) {
  return (
    <>
      <p className="section-heading">
        <Icon name="hash" size={14} /> Cipher Progress
      </p>
      <section className="cryptogram-board" id="cryptogram-board">
      {board.map((word) => (
        <div className={`cipher-word${word.complete ? " complete" : ""}`} key={word.mission_id}>
          <div className="cipher-letters">
            {[...word.display].map((ch, i) => (
              <span className={`tile${word.revealed[i] ? " revealed" : ""}`} key={i}>
                {ch}
              </span>
            ))}
          </div>
          <div className="cipher-word-title">{word.title}</div>
          {word.tagline && <div className="cipher-word-tagline">{word.tagline}</div>}
        </div>
      ))}
      </section>
    </>
  );
}
