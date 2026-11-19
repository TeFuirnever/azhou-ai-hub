# Agent Skin DSH restricted Dream live acceptance — 2026-11-18

## Scope

This receipt records a maintainer-Mac desktop observation of candidate `826e4e8be7737a2667db2e3ae6f35aa69ab3e9a1` on DeepSeek Harness `0.2.2-rc.1`, Agent Skin `0.9.0/build 43`. It covers one synthetic capsule using the supported literal-main profile, not arbitrary Dream CSS, media, all navigation states or complete V3 acceptance. The previous [file-install receipt](agent-skin-v3-file-install-2026-11-18.md) remains historical for `98249370`; it does not establish acceptance of later bytes.

Earlier candidates rejected Apply before database commit because the real host's semantic main uses `display: contents`, while the earlier browser fixture supplied a layout box. The accepted candidate maps that semantic anchor to its exclusive direct, box-bearing main panel, preserves the bounded host contract and fails closed on unsupported or changed topology. The regression fixture now exercises that topology through the embedded settings entry, but only the observations below are real desktop evidence.

## Observed sequence

| Step | Result |
| --- | --- |
| Launch | Loading plugins, Azhou startup canvas and wallpaper appeared in sequence. This was discrete observation, not continuous first-frame capture. |
| Apply synthetic capsule | The panel reported successful application and save; the main region visibly changed to synthetic blue and Restore became available. |
| Navigate | Plugins then New Session retained the synthetic blue appearance. This is not exhaustive navigation coverage. |
| Complete exit and relaunch | Native Quit was followed by a process check showing no DSH main/host process. After relaunch and startup animation, synthetic blue remained visible. |
| Restore | The panel reported the saved Azhou appearance restored. The original wallpaper and saved strength 42 returned; Restore was disabled. |
| Repeat import | Importing the same synthetic capsule succeeded without changing the current appearance or drafts. |

The test finished with settings and DevTools closed, the original appearance restored, empty input and no message sent. The synthetic sample remains in the local theme library. The active ChatGPT session was not stopped or changed. No test database records were manually rewritten.

## Runtime-resource identity

The native DevTools Sources panel exported the loaded source-mapped plugin `client.js` resource. Its 6,957,847 bytes had SHA-256:

`607118ebaaf527c905f41189ee778ef95df58624274118408b7b91fe4c19063f`

The exported resource and the installed candidate's `client.js` matched at recording time. This is evidence for the **source-mapped loaded resource**, not independent byte-level verification of the concatenated executing bundle. No console code or security-protection bypass was used to obtain it. Version/build labels alone were not used as payload identity evidence.

## Boundaries and custody

Not verified in this record:

- Native IME composition.
- Restored appearance across an additional second cold restart.
- Arbitrary Dream assets beyond the supported literal-main profile.
- Codex host runtime behavior or the later integrated candidate as a separately launched binary.
- Byte-level identity of the concatenated executing bundle.
- Continuous first-frame capture or exhaustive visual, accessibility and navigation acceptance.

The structured local observation was recorded on 2026-11-18 at 10:23 UTC and subsequently read back. Raw desktop evidence, exported source resource, local paths, private artwork, installation receipts and recovery packages remain maintainer-local and are not included here. This receipt is a sanitized description, not a redistribution grant. The source provenance and support matrix were reviewed together with this record. No runtime code, production package or installation ownership is changed by this documentation update.
