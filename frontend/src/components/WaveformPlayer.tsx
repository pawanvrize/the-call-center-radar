"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { usePlayer } from "./PlayerContext";
import { formatSeconds } from "@/lib/utils";

interface Props {
  audioUrl: string;
}

export default function WaveformPlayer({ audioUrl }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { register, setCurrentTime } = usePlayer();
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [time, setTime] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<import("wavesurfer.js").default | null>(null);

  useEffect(() => {
    if (!containerRef.current || !audioUrl) return;

    let disposed = false;
    let ws: import("wavesurfer.js").default | null = null;

    // Imported here rather than at module scope: wavesurfer touches browser
    // globals, and this file is still server-rendered even as a client
    // component.
    void (async () => {
      const { default: WaveSurfer } = await import("wavesurfer.js");
      if (disposed || !containerRef.current) return;

      ws = WaveSurfer.create({
        container: containerRef.current,
        height: 72,
        waveColor: "#94a3b8",
        progressColor: "#6366f1",
        cursorColor: "#e11d48",
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        // Streams via a real <audio> element, so the browser issues HTTP Range
        // requests instead of downloading the whole mp3 before you can scrub.
        backend: "MediaElement",
        url: audioUrl,
      });

      wsRef.current = ws;
      register({ seek: (seconds: number) => ws?.setTime(seconds) });

      ws.on("ready", () => setDuration(ws?.getDuration() ?? 0));
      ws.on("play", () => setPlaying(true));
      ws.on("pause", () => setPlaying(false));
      ws.on("finish", () => setPlaying(false));
      ws.on("timeupdate", (t: number) => {
        setTime(t);
        setCurrentTime(t);
      });
      ws.on("error", (e: Error) => setError(e?.message ?? "audio failed to load"));
    })();

    return () => {
      disposed = true;
      register(null);
      wsRef.current = null;
      ws?.destroy();
    };
  }, [audioUrl, register, setCurrentTime]);

  if (!audioUrl) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500 dark:border-slate-700">
        No recording linked to this call.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => wsRef.current?.playPause()}
          aria-label={playing ? "Pause" : "Play"}
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white transition hover:bg-blue-500"
        >
          {playing ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
        </button>
        <div ref={containerRef} className="min-w-0 flex-1" />
        <span className="shrink-0 font-mono text-xs tabular-nums text-slate-500">
          {formatSeconds(time)} / {formatSeconds(duration)}
        </span>
      </div>
      {error && (
        <p className="mt-2 text-xs text-red-600 dark:text-red-400">
          Audio error: {error}
        </p>
      )}
    </div>
  );
}
