import { ImageResponse } from "next/og";

export const alt = "VERA — Go beyond the stars. Earbud review intelligence with honest uncertainty.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: "100%", height: "100%", padding: 72, background: "#080b12", color: "#e8ecf0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 24, letterSpacing: 4 }}><span>VERA /</span><span style={{ color: "#a4b1c5", fontSize: 18 }}>THE REVIEW OBSERVATORY</span></div>
      <div style={{ display: "flex", flexDirection: "column", fontSize: 88, letterSpacing: -4, lineHeight: 1.08 }}><span>Go beyond</span><span style={{ color: "#84abff" }}>the stars.</span></div>
      <div style={{ display: "flex", borderTop: "1px solid #2e3f5c", paddingTop: 26, fontSize: 24, color: "#a4b1c5" }}>Earbud experiences. Clearer signals. Honest uncertainty.</div>
    </div>, size,
  );
}
