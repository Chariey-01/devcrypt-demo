import { useEffect, useState } from "react";
import { Icon } from "../icons";
import { setConnectionListener } from "../api";

// Ported from app/static/app.js's renderConnectionBanner(). Every poll tick's api() call feeds
// this via setConnectionListener, so a dropped connection is always visibly explained instead
// of the screen silently freezing.
export function ConnectionBanner() {
  const [down, setDown] = useState(false);

  useEffect(() => {
    setConnectionListener(setDown);
    return () => setConnectionListener(() => {});
  }, []);

  if (!down) return null;
  return (
    <div className="connection-banner">
      <Icon name="wifi" size={14} /> Connection lost — attempting to reconnect…
    </div>
  );
}
