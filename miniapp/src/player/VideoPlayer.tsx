import { useEffect, useRef } from "react";

/** Deliberately a plain `<video>` element, not a third-party player
 * library (Vidstack etc. - see README.md, "not yet finalized"): the
 * `/stream/{media_id}` endpoint already speaks standard HTTP `Range`
 * requests (`services/range_parsing.py`), which is all a native
 * `<video>` needs for seeking - adding a player library is a drop-in
 * upgrade later (HLS support, PiP chrome, speed controls) that doesn't
 * change anything about how this component gets its `src` or reports
 * progress, so it's not worth taking the dependency before it's needed.
 */
export function VideoPlayer({
  src,
  startAtSeconds,
  onProgress,
}: {
  src: string;
  startAtSeconds?: number;
  onProgress: (positionSeconds: number, durationSeconds: number) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hasSeekedRef = useRef(false);

  useEffect(() => {
    hasSeekedRef.current = false;
  }, [src]);

  return (
    <video
      ref={videoRef}
      src={src}
      controls
      autoPlay
      playsInline
      className="aspect-video w-full bg-black"
      onLoadedMetadata={(e) => {
        const video = e.currentTarget;
        if (!hasSeekedRef.current && startAtSeconds && startAtSeconds < video.duration - 5) {
          video.currentTime = startAtSeconds;
        }
        hasSeekedRef.current = true;
      }}
      onTimeUpdate={(e) => {
        const video = e.currentTarget;
        if (Number.isFinite(video.duration)) {
          onProgress(video.currentTime, video.duration);
        }
      }}
    />
  );
}
