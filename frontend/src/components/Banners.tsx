import { Icon } from "../icons";
import type { MissionStatus } from "../types";

export function Banners({ data }: { data: MissionStatus }) {
  return (
    <>
      {data.event_status !== "running" && (
        <div className="event-banner">
          {data.event_status === "not_started" || data.event_status === "draft" ? (
            <>
              <Icon name="radar" size={14} /> STANDING BY — waiting for the Game Master to start
              the event.
            </>
          ) : data.event_status === "paused" ? (
            <>
              <Icon name="octagon-alert" size={14} /> EVENT PAUSED by the Game Master.
            </>
          ) : (
            <>
              <Icon name="shield-check" size={14} /> EVENT ENDED — final scores are locked.
            </>
          )}
        </div>
      )}
      {data.broadcast && (
        <div className="broadcast">
          <Icon name="radio-tower" size={14} /> {data.broadcast.message}
        </div>
      )}
    </>
  );
}
