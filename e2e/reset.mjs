// Drop the end-to-end database so the backend seeds a fresh queue from data/.
import { rmSync } from "node:fs";

rmSync(process.env.UNDERCOVER_DB, { force: true });
