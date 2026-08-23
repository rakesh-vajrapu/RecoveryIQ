export default function Loading() {
  return <div className="space-y-6" aria-label="Loading page"><div className="shimmer h-3 w-36 rounded-full" /><div className="shimmer h-10 max-w-xl rounded-xl" /><div className="shimmer h-4 max-w-2xl rounded-lg" /><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="shimmer h-36 rounded-2xl" />)}</div></div>;
}

