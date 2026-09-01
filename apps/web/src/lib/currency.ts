export function formatMinorINRToFull(minorINR: number): string {
  const value = minorINR / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatMinorINRToCompact(minorINR: number): string {
  const value = minorINR / 100;
  if (Math.abs(value) >= 10000000) {
    const crores = value / 10000000;
    return `₹${crores.toFixed(2)} Cr`;
  } else if (Math.abs(value) >= 100000) {
    const lakhs = value / 100000;
    return `₹${lakhs.toFixed(2)} L`;
  } else if (Math.abs(value) >= 1000) {
    const thousands = value / 1000;
    return `₹${thousands.toFixed(2)} K`;
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}
