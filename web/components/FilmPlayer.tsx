"use client";

import { useState, type KeyboardEvent } from "react";

type Track = "en" | "am";
type Aspect = "16x9" | "9x16";

const SOURCES: Record<Aspect, Record<Track, string>> = {
  "16x9": {
    en: "/videos/red-through-the-years-16x9.mp4",
    am: "/videos/red-through-the-years-16x9-am.mp4",
  },
  "9x16": {
    en: "/videos/red-through-the-years-9x16.mp4",
    am: "/videos/red-through-the-years-9x16-am.mp4",
  },
};

const ASPECT_HINT: Record<Aspect, string> = {
  "16x9": "Landscape · desktop & wide screens",
  "9x16": "Portrait · phone / vertical feeds",
};

const TRACK_HINT: Record<Track, string> = {
  en: "Primary narration",
  am: "Second language · EN subtitles on",
};

const FilmPlayer = () => {
  const [track, setTrack] = useState<Track>("en");
  const [aspect, setAspect] = useState<Aspect>("16x9");
  const src = SOURCES[aspect][track];
  const isPortrait = aspect === "9x16";

  const handleSelectTrack = (next: Track) => () => setTrack(next);
  const handleSelectAspect = (next: Aspect) => () => setAspect(next);

  const handleKeyDownTrack =
    (next: Track) => (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setTrack(next);
      }
    };

  const handleKeyDownAspect =
    (next: Aspect) => (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setAspect(next);
      }
    };

  const aspectButtonClass = (active: boolean) =>
    active
      ? "rounded-sm bg-crimson px-4 py-2 text-sm font-semibold text-bone"
      : "rounded-sm border border-mist/20 bg-transparent px-4 py-2 text-sm font-semibold text-mist/80 hover:border-mist/40";

  const trackButtonClass = (active: boolean) =>
    active
      ? "rounded-sm bg-gold px-4 py-2 text-sm font-semibold text-ink"
      : "rounded-sm border border-mist/20 bg-transparent px-4 py-2 text-sm font-semibold text-mist/80 hover:border-mist/40";

  return (
    <div className="w-full">
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-mist/45">
            Format
          </p>
          <div
            className="flex flex-wrap items-center gap-3"
            role="tablist"
            aria-label="Video aspect ratio"
          >
            <button
              type="button"
              role="tab"
              aria-selected={aspect === "16x9"}
              tabIndex={0}
              aria-label="Show 16 by 9 landscape cut"
              onClick={handleSelectAspect("16x9")}
              onKeyDown={handleKeyDownAspect("16x9")}
              className={aspectButtonClass(aspect === "16x9")}
            >
              16:9 Landscape
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={aspect === "9x16"}
              tabIndex={0}
              aria-label="Show 9 by 16 portrait cut"
              onClick={handleSelectAspect("9x16")}
              onKeyDown={handleKeyDownAspect("9x16")}
              className={aspectButtonClass(aspect === "9x16")}
            >
              9:16 Portrait
            </button>
          </div>
          <p className="mt-2 text-sm text-mist/55">{ASPECT_HINT[aspect]}</p>
        </div>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-mist/45">
            Narration
          </p>
          <div
            className="flex flex-wrap items-center gap-3"
            role="tablist"
            aria-label="Narration language"
          >
            <button
              type="button"
              role="tab"
              aria-selected={track === "en"}
              tabIndex={0}
              aria-label="Play English narration"
              onClick={handleSelectTrack("en")}
              onKeyDown={handleKeyDownTrack("en")}
              className={trackButtonClass(track === "en")}
            >
              English
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={track === "am"}
              tabIndex={0}
              aria-label="Play Amharic narration"
              onClick={handleSelectTrack("am")}
              onKeyDown={handleKeyDownTrack("am")}
              className={trackButtonClass(track === "am")}
            >
              Amharic · አማርኛ
            </button>
          </div>
          <p className="mt-2 text-sm text-mist/55">{TRACK_HINT[track]}</p>
        </div>
      </div>

      <div
        className={
          isPortrait
            ? "film-shell mx-auto w-full max-w-[min(100%,420px)] overflow-hidden rounded-sm bg-ash"
            : "film-shell w-full overflow-hidden rounded-sm bg-ash"
        }
      >
        <video
          key={src}
          className={
            isPortrait
              ? "aspect-[9/16] w-full bg-black"
              : "aspect-video w-full bg-black"
          }
          controls
          playsInline
          preload="metadata"
          poster="/stills/hero.jpg"
          aria-label={`Red Through the Years — ${aspect} · ${track === "en" ? "English" : "Amharic"}`}
        >
          <source src={src} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>
    </div>
  );
};

export default FilmPlayer;
