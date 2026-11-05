import type { Origin } from "./types";
/** The literal bracketed string, so a grep over rendered text can check it. */
export const originText = (o: Origin) => `[${o}]`;
