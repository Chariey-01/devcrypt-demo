import { Icon } from "../icons";
import type { FragmentEntry } from "../types";

export function FragmentRail({ fragments }: { fragments: FragmentEntry[] }) {
  return (
    <>
      <p className="section-heading">
        <Icon name="file-lock-2" size={14} /> Recovered Fragments
      </p>
      <section className="fragment-rail" id="fragment-rail">
        {!fragments || !fragments.length ? (
          <span className="hint-text">
            <Icon name="file-lock-2" size={13} /> No fragments recovered yet.
          </span>
        ) : (
          fragments.map((f) => (
            <span className="fragment-chip" key={f.mission_id}>
              <Icon name="hash" size={12} /> {f.value}
            </span>
          ))
        )}
      </section>
    </>
  );
}
