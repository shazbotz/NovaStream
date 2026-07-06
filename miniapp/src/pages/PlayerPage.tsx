import { useEffect, useRef, useState } from "react";
import { getContinueWatching, getStreamToken, recordWatchProgress } from "../lib/api-client";
import { Header } from "../components/Header";
import { ErrorBanner, LoadingSpinner } from "../components/Feedback";
import { VideoPlayer } from "../player/VideoPlayer";

// Reports playback position at most this often - matches
// `continue_watching`'s purpose (resume approximately where you left
// off), not a frame-accurate log; every `onTimeUpdate` tick (multiple
// times a second) would just spam `POST /api/watch-progress` for no
// benefit.
const PROGRESS_REPORT_INTERVAL_MS = 10_000;

export function PlayerPage({ mediaId, title, onBack }: { mediaId: string; title: string; onBack: () => void }) {
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [resumeAt, setResumeAt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const lastReportRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setStreamUrl(null);

    Promise.all([getStreamToken(mediaId), getContinueWatching().catch(() => ({ items: [] }))])
      .then(([tokenRes, watching]) => {
        if (cancelled) return;
        setStreamUrl(tokenRes.url);
        const existing = watching.items.find((item) => item.media_id === mediaId);
        if (existing) setResumeAt(existing.position_seconds);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, [mediaId]);

  const handleProgress = (positionSeconds: number, durationSeconds: number) => {
    const now = Date.now();
    if (now - lastReportRef.current < PROGRESS_REPORT_INTERVAL_MS) return;
    lastReportRef.current = now;
    recordWatchProgress(mediaId, positionSeconds, durationSeconds).catch(() => {
      // Best-effort: a dropped progress report just means resume-from
      // is slightly stale next time, not worth surfacing to the user
      // mid-playback.
    });
  };

  return (
    <div className="pb-20">
      <Header title={title} onBack={onBack} />
      {error && <ErrorBanner message={error} />}
      {!error && !streamUrl && <LoadingSpinner label="Preparing stream..." />}
      {streamUrl && (
        <VideoPlayer src={streamUrl} startAtSeconds={resumeAt} onProgress={handleProgress} />
      )}
    </div>
  );
}
