import { useEffect, useState } from "react";

const LINES = [
  "DECK-OS v0.1 // kernel handshake ........ OK",
  "mounting /dev/neural0 .................... OK",
  "loading glyph rom [JBM-MONO] ............. OK",
  "spinning up crypto core [olm/megolm] ..... OK",
  "probing uplink ........................... OK",
  "routing via matrix relay ................. OK",
  "",
  "WELCOME BACK, OPERATOR.",
];

const LOGO = String.raw`
 ____            _    __  __
|  _ \  ___  ___| | _|  \/  | ___  ___ ___  __ _  __ _  ___  ___
| | | |/ _ \/ __| |/ / |\/| |/ _ \/ __/ __|/ _' |/ _' |/ _ \/ __|
| |_| |  __/ (__|   <| |  | |  __/\__ \__ \ (_| | (_| |  __/\__ \
|____/ \___|\___|_|\_\_|  |_|\___||___/___/\__,_|\__, |\___||___/
                                                 |___/`;

export function BootSequence({ onDone }: { onDone: () => void }) {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (shown >= LINES.length) {
      const t = setTimeout(onDone, 650);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setShown((n) => n + 1), 140 + Math.random() * 120);
    return () => clearTimeout(t);
  }, [shown, onDone]);

  useEffect(() => {
    const skip = () => onDone();
    window.addEventListener("keydown", skip);
    window.addEventListener("pointerdown", skip);
    return () => {
      window.removeEventListener("keydown", skip);
      window.removeEventListener("pointerdown", skip);
    };
  }, [onDone]);

  return (
    <div className="boot">
      <pre className="logo glitch" data-text={LOGO}>
        {LOGO}
      </pre>
      <div className="boot-lines">
        {LINES.slice(0, shown).map((l, i) => (
          <div key={i} className={l.startsWith("WELCOME") ? "accent" : undefined}>
            {l || " "}
          </div>
        ))}
        <span className="cursor">█</span>
      </div>
      <div className="dim boot-skip">[ press any key / tap to skip ]</div>
    </div>
  );
}
