export const subjectLabel = (s: string, L: (en: string, hi: string) => string) => {
  const m: Record<string, [string, string]> = {
    physics: ["Physics", "भौतिकी"],
    chemistry: ["Chemistry", "रसायन"],
    mathematics: ["Mathematics", "गणित"],
    biology: ["Biology", "जीव विज्ञान"],
    botany: ["Botany", "वनस्पति विज्ञान"],
    zoology: ["Zoology", "जंतु विज्ञान"],
  };
  const x = m[s.toLowerCase()];
  return x ? L(x[0], x[1]) : s;
};
