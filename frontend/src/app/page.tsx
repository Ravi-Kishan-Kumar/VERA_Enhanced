import { ReviewAnalyzer } from "@/components/ReviewAnalyzer";
import { pageMetadata } from "@/lib/metadata";

export const metadata = pageMetadata("Beyond the star rating", "Read the experience behind an earbud review with aspect sentiment and uncertainty-aware scores.", "/");
export default function Home() {
  return <><div className="page-heading home-heading"><div className="eyebrow"><span className="tiny-square" aria-hidden="true"/> THE REVIEW OBSERVATORY</div><h1>Go beyond <span>the stars.</span></h1><p>Understand what an earbud review actually says — with a score that shows its uncertainty.</p><div className="workflow-rail" aria-label="Analysis steps"><span><b>01</b> Read the review</span><span aria-hidden="true">→</span><span><b>02</b> Connect the signals</span><span aria-hidden="true">→</span><span><b>03</b> See the context</span></div></div><ReviewAnalyzer/></>;
}
