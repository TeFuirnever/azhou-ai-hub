import assert from "node:assert/strict";

import { exportRoute } from "../src/routes";

assert.equal(exportRoute.method, "POST");
assert.equal(exportRoute.path, "/v2/export");
assert.equal(exportRoute.resumable, false);
