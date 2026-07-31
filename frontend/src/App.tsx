import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { useMissionStatus } from "./hooks/useMissionStatus";
import { ConnectionBanner } from "./components/ConnectionBanner";
import { TopBar } from "./components/TopBar";
import { Banners } from "./components/Banners";
import { ScoreBreakdown } from "./components/ScoreBreakdown";
import { ProgressTracker } from "./components/ProgressTracker";
import { CryptogramBoard } from "./components/CryptogramBoard";
import { FragmentRail } from "./components/FragmentRail";
import { MissionPanel } from "./components/MissionPanel";
import { FinishedPanel } from "./components/FinishedPanel";

interface BoothTransition {
  completedTitle: string | null;
  nextTitle: string;
  boothsCompleted: number;
  boothsTotal: number;
}

interface KcCompleteBanner {
  title: string;
}

export default function App() {
  const { data, loading, refresh } = useMissionStatus();

  const [message, setMessage] = useState<string | null>(null);
  const messageTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  function showMessage(text: string) {
    setMessage(text || null);
    if (messageTimerRef.current) clearTimeout(messageTimerRef.current);
    messageTimerRef.current = setTimeout(() => setMessage(null), 4000);
  }

  const lastMissionIdRef = useRef<number | null>(null);
  const [boothTransition, setBoothTransition] = useState<BoothTransition | null>(null);
  const kcBannerShownForRef = useRef<Set<number>>(new Set());
  const [kcCompleteBanner, setKcCompleteBanner] = useState<KcCompleteBanner | null>(null);

  useEffect(() => {
    if (!data || !data.mission) return;
    const mission = data.mission;

    if (mission.id !== lastMissionIdRef.current) {
      if (lastMissionIdRef.current !== null) {
        const justCompleted = data.timeline.find((t) => t.mission_id === lastMissionIdRef.current);
        setBoothTransition({
          completedTitle: justCompleted ? justCompleted.title : null,
          nextTitle: mission.title,
          boothsCompleted: data.booths_completed,
          boothsTotal: data.booths_total,
        });
      }
      lastMissionIdRef.current = mission.id;
    }

    if (mission.knowledge_check_complete && !kcBannerShownForRef.current.has(mission.id)) {
      kcBannerShownForRef.current.add(mission.id);
      setKcCompleteBanner({ title: mission.title });
    }
  }, [data]);

  if (loading || !data) {
    return (
      <>
        <ConnectionBanner />
        <p className="hint-text" style={{ padding: "2rem" }}>
          <Icon name="radar" size={13} /> Loading mission status…
        </p>
      </>
    );
  }

  return (
    <>
      <ConnectionBanner />
      <TopBar team={data.team} />
      <Banners data={data} />

      {boothTransition && (
        <div className="narrative-message">
          <Icon name="check" size={13} /> Booth complete
          {boothTransition.completedTitle ? `: ${boothTransition.completedTitle}` : ""}.{" "}
          <Icon name="file-lock-2" size={13} /> Fragment collected. <Icon name="chevron-right" size={13} /> Next
          booth: <strong>{boothTransition.nextTitle}</strong>. <Icon name="crosshair" size={13} />{" "}
          {boothTransition.boothsCompleted} of {boothTransition.boothsTotal} booths completed.
          <button type="button" className="ghost" style={{ marginLeft: "0.5rem" }} onClick={() => setBoothTransition(null)}>
            Dismiss
          </button>
        </div>
      )}

      {kcCompleteBanner && (
        <div className="narrative-message kc-complete-banner">
          <Icon name="check" size={13} /> <strong>Knowledge Check complete.</strong>{" "}
          <Icon name="unlock" size={13} /> Coding challenge unlocked for {kcCompleteBanner.title}.
          <button type="button" className="ghost" style={{ marginLeft: "0.5rem" }} onClick={() => setKcCompleteBanner(null)}>
            Dismiss
          </button>
        </div>
      )}

      <ScoreBreakdown data={data} />
      <ProgressTracker data={data} />
      <CryptogramBoard board={data.cryptogram} />

      {data.finished ? (
        <FinishedPanel data={data} />
      ) : data.mission ? (
        <MissionPanel
          key={data.mission.id}
          data={data}
          teamName={data.team.name}
          message={message}
          showMessage={showMessage}
          onSubmitted={refresh}
        />
      ) : null}

      <FragmentRail fragments={data.fragments} />
    </>
  );
}
