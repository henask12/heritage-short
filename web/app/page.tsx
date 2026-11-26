import FilmPlayer from "@/components/FilmPlayer";

const HomePage = () => {
  return (
    <main>
      {/* Hero — one composition */}
      <section className="relative min-h-[100svh] overflow-hidden">
        <div
          className="absolute inset-0 scale-105 animate-drift bg-cover bg-center"
          style={{ backgroundImage: "url(/stills/hero.jpg)" }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-hero-veil" aria-hidden="true" />

        <div className="relative z-10 mx-auto flex min-h-[100svh] max-w-6xl flex-col justify-end px-6 pb-16 pt-28 md:pb-24 md:pt-32">
          <p className="animate-rise font-body text-xs font-semibold uppercase tracking-[0.28em] text-gold">
            The Heritage Short
          </p>
          <h1 className="animate-rise-late mt-4 max-w-4xl font-display text-5xl font-bold leading-[0.95] text-bone md:text-7xl lg:text-8xl">
            Red Through the Years
          </h1>
          <div
            className="animate-rise-later mt-6 h-px w-28 origin-left bg-crimson animate-pulse-line"
            aria-hidden="true"
          />
          <p className="animate-rise-later mt-6 max-w-xl text-base leading-relaxed text-mist/85 md:text-lg">
            A boy in Addis Ababa falls for Manchester United — the Red Devils —
            and carries that loyalty through glory, drought, and adulthood.
          </p>
          <div className="animate-rise-later mt-8 flex flex-wrap gap-3">
            <a
              href="#watch"
              className="rounded-sm bg-crimson px-6 py-3 text-sm font-semibold text-bone transition hover:bg-ember"
              tabIndex={0}
              aria-label="Jump to watch the film"
            >
              Watch the film
            </a>
            <a
              href="#story"
              className="rounded-sm border border-mist/25 px-6 py-3 text-sm font-semibold text-mist transition hover:border-mist/50"
              tabIndex={0}
              aria-label="Jump to the story section"
            >
              Read the story
            </a>
          </div>
        </div>
      </section>

      {/* Watch */}
      <section
        id="watch"
        className="relative bg-section-glow px-6 py-20 md:py-28"
      >
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-3xl font-bold text-bone md:text-4xl">
            Watch
          </h2>
          <p className="mt-3 max-w-2xl text-mist/75">
            About ninety seconds. Switch 16:9 or 9:16, English or Amharic.
            English subtitles stay on either way.
          </p>
          <div className="mt-10">
            <FilmPlayer />
          </div>
        </div>
      </section>

      {/* Story */}
      <section id="story" className="px-6 py-20 md:py-28">
        <div className="mx-auto grid max-w-6xl gap-12 md:grid-cols-[1.1fr_0.9fr] md:items-center">
          <div>
            <h2 className="font-display text-3xl font-bold text-bone md:text-4xl">
              What this film is about
            </h2>
            <p className="mt-5 text-base leading-relaxed text-mist/80 md:text-lg">
              <span className="text-bone">Red Through the Years</span> is a
              heritage short: supporting Manchester United not as a scoreline,
              but as something a family can pass down — patience, belonging, and
              the decision to stay when the easy wins stop coming.
            </p>
            <p className="mt-4 text-base leading-relaxed text-mist/70 md:text-lg">
              It begins with an oversized United shirt in Addis Ababa, moves
              through match nights and lean seasons, and ends in the present:
              still a Red Devil before the whistle.
            </p>
            <ul className="mt-8 space-y-3 text-sm text-mist/65">
              <li>
                <span className="font-semibold text-gold">Audience:</span>{" "}
                anyone who understands lifelong loyalty — fans and non-fans.
              </li>
              <li>
                <span className="font-semibold text-gold">Intent:</span> leave
                you feeling that club support can be family heritage.
              </li>
              <li>
                <span className="font-semibold text-gold">Length:</span> ~60–90
                seconds · 16:9 and 9:16 both playable above.
              </li>
            </ul>
          </div>
          <div className="relative overflow-hidden rounded-sm">
            <img
              src="/stills/mid.jpg"
              alt="Still from Red Through the Years — adult fan in a Manchester United jersey"
              className="h-full w-full object-cover"
            />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink/70 to-transparent" />
          </div>
        </div>
      </section>

      {/* How it was made */}
      <section id="made" className="border-t border-mist/10 bg-ash/60 px-6 py-20 md:py-28">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-3xl font-bold text-bone md:text-4xl">
            How it was made
          </h2>
          <p className="mt-4 max-w-3xl text-mist/75">
            This is an AI-assisted short built as a reproducible pipeline for
            TenX B2W0 — not a single-click generate. Every stage reads one
            storyboard contract.
          </p>
          <div className="mt-10 grid gap-8 md:grid-cols-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-crimson">
                Voice
              </p>
              <p className="mt-2 font-display text-xl text-bone">Gemini TTS</p>
              <p className="mt-2 text-sm leading-relaxed text-mist/65">
                English and Amharic narration with stock voices — no voice
                cloning.
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-crimson">
                Picture + motion
              </p>
              <p className="mt-2 font-display text-xl text-bone">
                Keyframes → motion
              </p>
              <p className="mt-2 text-sm leading-relaxed text-mist/65">
                Generated stills animated into cinematic dual-plate camera moves
                (Wan/Veo upgrade path documented in the repo).
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-crimson">
                Edit
              </p>
              <p className="mt-2 font-display text-xl text-bone">FFmpeg</p>
              <p className="mt-2 text-sm leading-relaxed text-mist/65">
                Soft original anthem-style score under the voice (not the
                official club theme), −14 LUFS, EN subtitles, AI end card.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Disclosure / footer */}
      <footer className="border-t border-mist/10 px-6 py-14">
        <div className="mx-auto flex max-w-5xl flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-display text-2xl text-bone">Red Through the Years</p>
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-mist/60">
              AI-assisted short film. Characters are fictional. No living
              footballer faces are depicted. Manchester United / Red Devils
              appear as story wardrobe and atmosphere. Full ethics and pipeline
              notes live in the public GitHub repo.
            </p>
          </div>
          <div className="flex flex-col gap-3 text-sm">
            <a
              href="https://github.com/henask12/heritage-short"
              className="font-semibold text-gold underline-offset-4 hover:underline"
              tabIndex={0}
              aria-label="Open the heritage-short GitHub repository"
              target="_blank"
              rel="noreferrer"
            >
              View source on GitHub
            </a>
            <p className="text-mist/45">TenX B2W0 · The Heritage Short</p>
          </div>
        </div>
      </footer>
    </main>
  );
};

export default HomePage;
