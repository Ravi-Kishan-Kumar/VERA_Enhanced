import { ImageResponse } from "next/og";

export const alt = "VERA: Go beyond the stars. Earbud review intelligence with honest uncertainty.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: "100%", height: "100%", padding: 72, background: "#f7f2e8", color: "#302a24" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 24 }}><span>VERA</span><span style={{ color: "#756b61", fontSize: 18 }}>REVIEW INTELLIGENCE</span></div>
      <div style={{ display: "flex", flexDirection: "column", fontFamily: "Georgia, serif", fontSize: 88, letterSpacing: -4, lineHeight: 1.02 }}><span>Go beyond</span><span style={{ color: "#a34f2b" }}>the stars.</span></div>
      <div style={{ display: "flex", borderTop: "1px solid #d9cfc1", paddingTop: 26, fontSize: 24, color: "#756b61" }}>Earbud experiences. Clearer signals. Honest uncertainty.</div>
    </div>, size,
  );
}
