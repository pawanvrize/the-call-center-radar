// The live pipeline — POST /ingest.
//
// Deliberately the same code path the overnight batch uses. If a recording the
// system has never seen comes back with verified citations, the precomputed
// 1,441 calls are demonstrably not a lookup table.
import IngestForm from "@/components/IngestForm";

export const metadata = {
  title: "Analyse a new call · Call-Centre Radar",
};

export default function IngestPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Analyse a new call</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload a recording the system has never seen. It runs the same
          pipeline as the other 1,441 calls — channel split, transcription, mood
          scoring, change-point detection, grounded reasoning, and citation
          verification — then opens the analysed call.
        </p>
      </div>

      <IngestForm />

      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <p className="font-medium text-slate-700 dark:text-slate-300">
          What happens to the recording
        </p>
        <p className="mt-1">
          It is stored alongside the corpus so the call is playable afterwards,
          and the customer appears in the customer list with their new call. The
          audio must be stereo — this system relies on channel separation
          (left&nbsp;=&nbsp;agent, right&nbsp;=&nbsp;customer) rather than
          diarization, so a mono file is rejected rather than mis-attributed.
        </p>
      </div>
    </div>
  );
}
