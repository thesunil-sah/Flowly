// Pure-CSS pulsing live indicator — the one continuous animation the motion
// rule allows; motion-reduce turns it into a static dot.
export function LiveDot() {
  return (
    <span className="relative flex size-2.5" aria-hidden>
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60 motion-reduce:animate-none motion-reduce:opacity-0" />
      <span className="relative inline-flex size-2.5 rounded-full bg-success" />
    </span>
  );
}
