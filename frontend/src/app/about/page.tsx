import { pageMetadata } from "@/lib/metadata";
import Link from "next/link";

export const metadata = pageMetadata("Methodology", "How VERA combines review signals, aspect sentiment, and honest uncertainty, with transparent model limitations.", "/about");

export default function AboutPage() {
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow"><span className="tiny-square" aria-hidden="true" /> METHODOLOGY</div>
        <h1>How VERA reads a review.</h1>
        <p>A star rating is a single click. VERA estimates the experience the text describes — and says how sure it is.</p>
      </div>

      <div className="prose">
        <section>
          <h2>Why not trust the stars?</h2>
          <p>
            Star averages hide <em>which</em> part of a product disappointed. Small samples can also make a product
            look more certain than its reviews justify.
          </p>
        </section>

        <section>
          <h2>Seven signal agents</h2>
          <ol>
            <li><strong>Preprocessor</strong> — cleans text, detects language, and flags reviews that may not be about earbuds.</li>
            <li><strong>Experience extractor</strong> — a fine-tuned DeBERTa-v3 model estimates the experience score from text alone.</li>
            <li><strong>Aspect sentiment</strong> — ten earbud aspects (sound, bass, battery, comfort, fit, build, connectivity, microphone, noise cancellation, value).</li>
            <li><strong>Consistency</strong> — measures how far the star is from the text.</li>
            <li><strong>Review quality</strong> — helpful votes, verified purchase, freshness, and length become a trust weight. Missing details are filled with training averages.</li>
            <li><strong>Domain rating</strong> — a text model that learns rating patterns from earbud reviews.</li>
            <li><strong>Fusion</strong> — a 20-model XGBoost ensemble combines all signals into the corrected score.</li>
          </ol>
        </section>

        <section>
          <h2>Honest uncertainty</h2>
          <p>
            Split-conformal calibration targets <strong>90% coverage</strong> of held-out reference labels. Measured
            coverage is reported by evaluation runs; the interval does not mean a single prediction is 90% likely to
            be right. Interval confidence describes how narrow it is.
          </p>
        </section>

        <section>
          <h2>Fair product rankings</h2>
          <p>
            Product scores use <strong>Empirical Bayes</strong> shrinkage: a product&apos;s trust-weighted mean is pulled
            toward the average of all products in proportion to how noisy it is. A small or inconsistent review set
            has less influence and carries more uncertainty.
          </p>
        </section>

        <section>
          <h2>Limitations</h2>
          <ul>
            <li>&ldquo;Experience&rdquo; has no established ground truth. Training labels are LLM-generated, and the reference annotations used for agreement are from Claude, not human reviewers. Agreement measures consistency with that model reference, not human validation.</li>
            <li>Models are trained on English Amazon earbud reviews; other languages and product types are flagged, not reliably scored.</li>
            <li>Review quality is a weighting signal. It does not verify purchases or detect fake reviews.</li>
          </ul>
        </section>

        <Link href="/" className="text-link">Analyze a review ↗</Link>
      </div>
    </>
  );
}
