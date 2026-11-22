"""Integrity suite for the super-diagram-design canonical skill.

Pins the vendored upstream baseline (cathrynlavery/diagram-design at the
immutable provenance commit, frontmatter metadata version "2.6"; the
upstream published no tag or release as of 2026-11-22, so the pin is the
main tip recorded that day), the hub packaging layer (frontmatter contract,
brand protocol, receipt), the fail-closed setup boundary and the retained
license copy the receipt depends on.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.check_repository import INSTALLABLE_SKILL_PATHS, INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-diagram-design"
SKILL = SKILL_DIR / "SKILL.md"

UPSTREAM_COMMIT = "d7b0176d7e60c6f2ff54067991491ac7622c81fb"
UPSTREAM_SKILL_SHA256 = "0f8159717762225aad4f8aec9162ffecd1ad19f12f41157c5874dfc047017cc1"
UPSTREAM_LICENSE_SHA256 = "bb7e12e91fecef43024111123ff784cec6c485585561d8b552557c0173b3ed29"
UPSTREAM_THIRD_PARTY_LICENSES_SHA256 = "ad931154e2f91bf545fc9c442666a2159aa56c0af3cca0b7246e02c6efeab6ba"

# One pin per shipped package file. Every vendored file's pin is the upstream
# byte digest at UPSTREAM_COMMIT, with two groups of exceptions: SKILL.md's
# pin is the landed packaged bytes (upstream body plus the recorded packaging
# increments; the unmodified upstream digest is UPSTREAM_SKILL_SHA256), and
# the hub-authored records (THIRD_PARTY_LICENSES.md is upstream, the three
# references/provenance, setup and upstream-compatibility files are not).
PINNED_SHA256 = {
    "LICENSE": "bb7e12e91fecef43024111123ff784cec6c485585561d8b552557c0173b3ed29",
    "SKILL.md": "c483eec39a6cbfbe660a987b9eb68322b6eae1ac715e7b29a446bf686cfac068",
    "THIRD_PARTY_LICENSES.md": "ad931154e2f91bf545fc9c442666a2159aa56c0af3cca0b7246e02c6efeab6ba",
    "assets/example-arc-diagram-dark.html": "acd6b0c9d174b7d915d1e4e1a98a6019c30b02b8e5264f53f4ef2657dcbde77e",
    "assets/example-arc-diagram-full.html": "e785227378c5bde8a09d323ba743cf0f53b8dccb5e029325e99cccaed6a8f669",
    "assets/example-arc-diagram.html": "49044919cbfcdbd2b4b6025df2d52e42a553dddbf2fde2523e5185ba8d5cec08",
    "assets/example-architecture-containment-dark.html": "853399a330a541d63d5ca05834bb9f1545364fff61546754190899a49e54d28a",
    "assets/example-architecture-containment-full.html": "4b96ed9774d236c3b4968a10be0f7b5c8805095b0206d249bd8e53b4e893debe",
    "assets/example-architecture-containment.html": "10013c62e6449880627c2271edacfdc094f006a16e365a55f117e844097fe2de",
    "assets/example-architecture-dark.html": "b471f857f2d8745705925ee49659d8506de291c3a7b3761a3fb47a0394b9c8df",
    "assets/example-architecture-delta-dark.html": "d3f0984c7ff145656bb400ff294e9595d7f5f1209d156edbb5e5676e8ee199b9",
    "assets/example-architecture-delta-full.html": "cd23ff4b3dcc2a734a13ab31807ce46c1e26dd82c3a91bac7b161f0d3abaeea0",
    "assets/example-architecture-delta.html": "0a88e1e44fcac97be87accccb429c4930380938f59534468090e82c45ceabfc6",
    "assets/example-architecture-full.html": "6c3951cbb3cdb94b1825efbfabbf5dda996c20106f00fa1d06511d58792b0248",
    "assets/example-architecture.html": "a9e8b59854d31e70288abba522509494f82a319bc684c3694e08e67dfc990bc5",
    "assets/example-axonometric-plan-campus-animated.html": "72420915d79afb6daaa6f6215ac08754b4d2dc02b8c844cb5e25b52771002350",
    "assets/example-axonometric-plan-campus-dark.html": "7d13e33fcfa93e177179c357c0ad884fbb73d826ba79123420ad513ea174ba7c",
    "assets/example-axonometric-plan-campus-full.html": "e1d28913537b8e206af137c8e6fbc212cb47203de3f69baa4fac2cee96beea19",
    "assets/example-axonometric-plan-campus.html": "5d03a724dd85ec929dd17643294dbec7a6fd6165ee010fd0fef44dc72bdf1e31",
    "assets/example-axonometric-plan-coffee-shop-animated.html": "7c948dc5daf9c9568c6ce1b22fae4c2b0c0c330794785f767655ebaf7da6e70e",
    "assets/example-axonometric-plan-coffee-shop-dark.html": "0d5836e9b4ca2f85c4a1fd976ef0b7f89a29a29fb169dcb59b483a4e731bd46b",
    "assets/example-axonometric-plan-coffee-shop-full.html": "ba03f90070b4bda66dc8cdbe3ba8334fadfa77e94f8ddde3d3aa3aa6b4d97e5a",
    "assets/example-axonometric-plan-coffee-shop.html": "90f8f78c306ea5b96b64c6c5c5e68c85e13fdd9a4f40aecc25dccf1f9b34283e",
    "assets/example-axonometric-plan-dark.html": "fa041519f9e71e518069334397886c6e545f9286b28dcdbc254a6aaa96a1034a",
    "assets/example-axonometric-plan-full.html": "13a7506ec0f4576a4f10313ba954b9c85a88bda258542c0c2017189f15a06adc",
    "assets/example-axonometric-plan-warehouse-animated.html": "e43acc91d852143ea615cd30b4251627a3e1224c95e433565c185bb4045620f6",
    "assets/example-axonometric-plan-warehouse-dark.html": "a85d79254ec2e1813a13055efb9951b84ea55a04f43aa6fb6c880aa448924d38",
    "assets/example-axonometric-plan-warehouse-full.html": "596cf38433b5c5a3c0a1af348863a61e6c31ecff3c1b46e04d989b10822c37a5",
    "assets/example-axonometric-plan-warehouse.html": "aed38ba8afc9c560fe22c7cbba1448e3c8f0efe43853d2c457b32e76d1bfef76",
    "assets/example-axonometric-plan.html": "1ffd4767dbb9c0fd49190582a7304d0aac4cd6df7cd7d538eb6e84cd1803f30a",
    "assets/example-bar-dark.html": "fb96534eff0910a006dabca940d71aeb1019076abfbe9a020758747c2e2cbb0a",
    "assets/example-bar-full.html": "ac8eff087cc5f2f04cffda1cb63b4e95641e9b05ca151a580e4df0016ddd08e1",
    "assets/example-bar.html": "b82fea59d393f0754f1543cf1e8d9189542fb93cf458bcd256a0c56fa060461b",
    "assets/example-beeswarm-dark.html": "597cf05ad582eb0dbe8040949c6f164096ce84631e6d3ba85d5fbf778d2b1dc7",
    "assets/example-beeswarm-full.html": "515edbc59376ad9bc99afc8cf9d55c0fa6a7e68f8eca95a02cf282086857e6cc",
    "assets/example-beeswarm.html": "e69a9b7ac33fae509c02a1ef06b39e1a548cd3925644e7cefd3ff2119a88a060",
    "assets/example-box-plot-dark.html": "28bc2a9b9df1e715b07c11a57b2ab8d0ee59ed5ebc782dacd74f3401e0cdd39b",
    "assets/example-box-plot-full.html": "a9bf7fc36d4db874b0fda6d27140fb6d3b9e51b06b13ca657e8dfb414a5fe617",
    "assets/example-box-plot.html": "16449419e0cca7dc153bc23c9c416dcb149ddcdfe4ca45c9535708719aa0b909",
    "assets/example-bubble-dark.html": "e5297625f2a81cebcd63250dcd7455f5c84160da501354f530dfcf59baf0ab9e",
    "assets/example-bubble-full.html": "6aaf526da9c9eccb82c3f88d502e831268003c01f1de6cdc171b2a8970b03b99",
    "assets/example-bubble.html": "48f6b009e1a05d780a66a8f9f3c3c9323da5aa3a6f7f6c50003558b4ba163657",
    "assets/example-bump-dark.html": "0e1ed31a2850405f60a00df02942532642bcd1bd5c2d728721e2087045c12840",
    "assets/example-bump-full.html": "aa62110a0d9dc11b19477013de1da1e09d37efb58f1b56b4af47fe9e80a7de0f",
    "assets/example-bump.html": "cdf62733836ff70f2b04e3a9062609b24f17d3b8be60d110a8182f9bc12a02a7",
    "assets/example-data-flow-dark.html": "a3f5f27b4a690a6d806c735bf2db42b1e3d7f235387018200830329379829917",
    "assets/example-data-flow-full.html": "606d1f7650ea6db8e84f977beb591616fa32df9bc3085c09072da81885db5133",
    "assets/example-data-flow.html": "f65978b77410fff9993fc099f4cf0d25bcaf67ce98fea2e281976e2406783b99",
    "assets/example-datalake-dark.html": "7eb08a81b703a1fb87877d33c79c0f31fcbd9a8fbc1dac20646e3f68aff93404",
    "assets/example-datalake-full.html": "f978706df71ffcdd6b2408aaeab78360ad68010487b9a849459219cd8cb8f5a3",
    "assets/example-datalake.html": "311b9143dc66cb96d7fe1ca3fa6d9cbf17b864976b8168ee3e8e8c497fe264d6",
    "assets/example-db-schema-dark.html": "c1f566f092642c8c58969b7609598272ea78eae5beb172f35afe1d1366078c6a",
    "assets/example-db-schema-full.html": "897c88e8cde6537409e0b0359495dfa33e658dc40581fdf0039bc65a0433cd25",
    "assets/example-db-schema.html": "5b65adae081c31b8f4a9772d8ba4a4066e759625197e2111885ac503cf8c2104",
    "assets/example-dependency-dark.html": "2e7f6d263d67bd751ca8d00111dcccd4a6a18d4d4241a709321cd043b630785d",
    "assets/example-dependency-full.html": "8498d290f2a74e85e99836ca1146879c6068e476ac8f2a847daa837c4cd1cd7d",
    "assets/example-dependency.html": "c75e1d72834ed4bbdd57f7470136d272f13d0cc7c41b02e84ae187553a6e893b",
    "assets/example-deployment-dark.html": "2c0c99d16f6d85fac54552bd4fe102ce9e0286fdf8eabd97ab4d90e5a97667e6",
    "assets/example-deployment-full.html": "9187eaafb9107e979c2e43bcde77edf63e974fc59cf72a50fef33ea8df460650",
    "assets/example-deployment.html": "8e4cee0bc1105dcd040b19d0000f84c69f81bde75d4cb16d2261fab617a7aee5",
    "assets/example-dp-integration-dark.html": "d28f525d2c7d0666b61d6e80133d006da942f1dfeefa41b0c8d32faf2120ca64",
    "assets/example-dp-integration-full.html": "fa9393528e19170873437c3f661fb7aa3cbaa94fa4001985f9d8faa7479708c6",
    "assets/example-dp-integration.html": "d521d09532183ee10d5ebdcea9cbc509a45d90cd85c35973ba40dbe94f338291",
    "assets/example-dp-security-matrix-dark.html": "1d93ac4553013cbb5d5fe962517601a0dadf03a8d1bf9ae522f10d7a83e05968",
    "assets/example-dp-security-matrix-full.html": "8f34f504368ba9fd13c2bb20b028d2fc27800fbb46c238e73b0aa65101ca4ad0",
    "assets/example-dp-security-matrix.html": "9ae674dcec652483ea75a9368f88fd4c61a447b34354b2f2386049c10491e83f",
    "assets/example-er-dark.html": "c007c14d88a48a8ea30b1144dd4ac392ee7891a2278262e2a6f6836b43aa7fdf",
    "assets/example-er-full.html": "e778b7e790c3fd3f9219807aef3115bda4d7b1efb9998df413bcd224f77ed163",
    "assets/example-er.html": "dcbca24c5eeeb84711510a60fae190754503f9b57d9551936b086f3fb589f617",
    "assets/example-event-modeling-dark.html": "367030eae9b906d2553b2e54cf83ce676b48d14dc219d29f51fd1cd6526810de",
    "assets/example-event-modeling-full.html": "d36023c30ecc3a7c1af61ead4fcb6fb2ddafb1793731bd71d1ee55eb3941a6f0",
    "assets/example-event-modeling.html": "142b4e758159448e05d31a3b3c55e0da12662920bd22bc9bd21c01cd85abeb74",
    "assets/example-exploded-ai-stack-animated.html": "f8448f23ac359dc698cf19a1288080f1f804fb8f157fbc830aa7d50fc1c930a0",
    "assets/example-exploded-ai-stack-dark.html": "2c249164a0959ad426b7d6e071c5c66fc05037e6a425601ea1b90025b81f29b0",
    "assets/example-exploded-ai-stack-full.html": "0f1ba200c4f6391fde4e1b350889ec50d63c4c1ead0fee680b1bcf4b4e9cce6f",
    "assets/example-exploded-ai-stack.html": "d2ac4530f8e3fb8eb9b4f344704ab9c36c3e983e6e5f8725250df1aa06b0ef2b",
    "assets/example-exploded-dark.html": "408cdc4779bf0db7456cdda4651cd1678adbb129c5c06ba6bf0d6632b544770c",
    "assets/example-exploded-full.html": "3f1ab91f536a6dd3547a61e2150b31a49bf9ba154ecc6f3bb813fd3d9269f16c",
    "assets/example-exploded-keyboard-animated.html": "7fac285e6daf22592a35cf1dedd6c54673923815b6c1f2ab20477464978e7566",
    "assets/example-exploded-keyboard-dark.html": "95ab0d91853a75c45e8b66de73373ae55bcd71fb722fda15ad586b6b0c04b0b4",
    "assets/example-exploded-keyboard-full.html": "8b1fb4cee1d8a80f710296cdf25e3985ae4041a3b6a3084b35e8e695de3527ca",
    "assets/example-exploded-keyboard.html": "858d60f2af6025301751a296125aca03cd7ea253d3efa8fef0e74df953992dc8",
    "assets/example-exploded-phone-animated.html": "de0bb80121f68b34449a08f028da0d1b5007aae88848ae79c8db7419a8d77067",
    "assets/example-exploded-phone-dark.html": "7dc2c3785b4456b54229f8c5fe56a22253614fc464ba7550e7f73c0619c21731",
    "assets/example-exploded-phone-full.html": "87c750c84a4e8811e09eef44cb9fba5567ff7fbc559718683b92922b954f6c4f",
    "assets/example-exploded-phone.html": "3866a52045df1b95333b09347b010871a73422f785bd7aad5de14fcf1f2189ef",
    "assets/example-exploded-unboxing-animated.html": "b0b081c3435ec728c776638757f69b8bbe286d40eadcafb0c1816d65b315eb00",
    "assets/example-exploded-unboxing-dark.html": "3bbe1e9be1c611e49796bdfe47bf69c714ec5e0ff5a13921cce548cfafe94f0b",
    "assets/example-exploded-unboxing-full.html": "601554b9fc46d378031b89f78454a595821a0a693d4eeb916c088d2ec157c628",
    "assets/example-exploded-unboxing.html": "9cbec60cb42ca24315f5e3392485699d24a3d22cd0879e128eae5d3988b4333f",
    "assets/example-exploded.html": "07eb320afdaa31516c221a80a9ae6a8e72be62185a8b790841237db823ef638a",
    "assets/example-fishbone-dark.html": "f884b81b83f7ce40cf85b8aa6c3a55db99b7fb2d38502deff222aaff36d7db47",
    "assets/example-fishbone-full.html": "cb55d2df262eec426d61503758aaef8c1f31322e71ac8fec5a2912655bfc337c",
    "assets/example-fishbone.html": "d0925f006f7ae339b7e3467886dc069e73def905e1316a5de00b2baeb61a63b2",
    "assets/example-flowchart-dark.html": "9b69415f880744d1c3dff23cf1dfa6bfbcc3bf38178456ce6668a74b783647ef",
    "assets/example-flowchart-full.html": "68bdada8201f46df8c76aa27be10194bc8d870a683696d400435817a19f0b696",
    "assets/example-flowchart.html": "f9c92596d77b010417b78f710ae96cf161395831ad8e51153caa41fa4a31446c",
    "assets/example-gantt-dark.html": "777c051f19001dbfdf9ced01d836622bda2ee5ad9d2d753012cd6f23fdde70d4",
    "assets/example-gantt-full.html": "171c7bed870d24976124e3f56aa884bd107d46380dd212bb0300fd92badd91b2",
    "assets/example-gantt.html": "4e017a543771aec9338e15df3be5f9278fa4883e306373c4ea0555b65c7c43a4",
    "assets/example-heatmap-dark.html": "6ec2953db65dbabcdbd5abe3d43f7e001524317ddd3e1230398f9de927e547c0",
    "assets/example-heatmap-full.html": "f3b92bf979a5504fd2c5bc4c107830ec50b43cc6685f662976a28739c9691f2d",
    "assets/example-heatmap.html": "18ee707bd2235b0530250218a4aa98574db42abcbfa02dae92c70b48cb0261da",
    "assets/example-high-level-dark.html": "d47d9056f2972d8ae68ddaabefdaf65c644cfafa2e19123e9ee0a675d19a0438",
    "assets/example-high-level-full.html": "359dc10e77c8de97550dbfab993c4ce4d683bd089a44302e20c1dcd4ad27501e",
    "assets/example-high-level-vertical-dark.html": "aabf08d05808d96ef6c5b16395830234022ce1f48abf8c56b2719acdde9a8aa2",
    "assets/example-high-level-vertical-full.html": "70a7fd733caba9e8c1bd05ea96b10bb22cb15594f24435058acfd4735f6fa3ae",
    "assets/example-high-level-vertical.html": "371385a4fd00a7d9f3896ac44417352bd7276e86488c3f4eaa72bd6df2902ae7",
    "assets/example-high-level.html": "7fc2cd00413de7a5221dde192403f87a8bef883984f8331f64c56f3bc387fa5e",
    "assets/example-import-drawio.html": "4404af257bf1216ef9959f3340cd82f2117d29d548b571e94ccf7931d4dd6bcd",
    "assets/example-import-excalidraw.html": "8a09e53ae6b0efbb9360784917117e784f90da53a4cc1de2a838e3ccef57d712",
    "assets/example-import-mermaid.html": "ed6109da74fe8fa2f5d6385ef1dda20e1b2d95c3e3d2d274499362de1aa20db9",
    "assets/example-import-plantuml.html": "95cc95bca1bbfc327e442783c71427fabe02383a0d0793bd91fd7b2e5c474106",
    "assets/example-it-state-dark.html": "3b571ce2bc0810586d8c125936fa1d90a898bad74b1079a6d8c6699024ae4c15",
    "assets/example-it-state-full.html": "ca864942c8d70da13e2ee19a35661c45be8c42ae79317eb08da2b1f5689a51ba",
    "assets/example-it-state.html": "9a91ec8959b77734745ddfa19f3dbf2992a3bf1134cb7352b9778ab3253e8d5b",
    "assets/example-journey-dark.html": "c1866ca355d8859d27f6e99d9e2415daf204c313ed4463ae9663ba9e930a9949",
    "assets/example-journey-full.html": "e739a7a1dbdd24bd3d9faae798ca02ed7d25b6e6944db1f43307287d541b348d",
    "assets/example-journey.html": "3703a5f553e1daabbf17d9785626ab63508bde326967bbce1390c1a72a0f2b37",
    "assets/example-kanban-dark.html": "30809cae8600a1852131362df275d9ab1c6aeedc65d3855caed264d48e19f5dc",
    "assets/example-kanban-full.html": "e557f78ae75b4f088f148ff7e3006d8c4aa0f8dfc0824e237ba656eb566021f8",
    "assets/example-kanban.html": "9171e229f6ca68c228a8ab3f47bd4a4b69f2ea77c2738282713a5f6271b32e1e",
    "assets/example-layers-dark.html": "412df7b0710cf14cd95c1e806e708241bda6b3bc8e1f142107adf857ed6aa7d1",
    "assets/example-layers-full.html": "6d9a2dc1eaa4f2d7309d93b8dedb9e379bb9debe42787030ee474725d26e68d8",
    "assets/example-layers.html": "e4edabd125d9d9de3e27d2a530b7e791042910e97ec71c3d8e23912eafda5082",
    "assets/example-line-dark.html": "552abdcac08788dac5ee7fa419ab854c5e09451b69822eb48935712880382a9d",
    "assets/example-line-full.html": "d121a15bc242986e2ce490ea34623ceba4eca96d6e16a531ab985fbc60dfd079",
    "assets/example-line.html": "8d53adb388306a8593a72c4eea063b8a95a0ba79d2134f51313a645c2554e227",
    "assets/example-loop-dark.html": "8ef6feecb47dc6043e1a7714fd0a795e357d484d38df35b594be85105029eb01",
    "assets/example-loop-full.html": "975a0d3e2954b928473fdc4e6e1720c84ebf23a84cc295434ea2ec74894d4cc5",
    "assets/example-loop-terminal.html": "93a2f86cca043537bf472973c6c1d51de54d85208ec54cd448c40e3f09aa73e8",
    "assets/example-loop.html": "7346157c67b6994b274772d0ffeb6c5ae2e935991246bd541e4aab84e31f3a8d",
    "assets/example-marimekko-dark.html": "91371c8c9915cd5a9fa5d04ddd425d2a17df8b495e2c1a195de8e73130bb3f44",
    "assets/example-marimekko-full.html": "e809f059a9df5634a62bcf0444311bb391b2168b45f4c4d4842a2692f1ff48b5",
    "assets/example-marimekko.html": "2b1407bcdc69114d3c74ac4a7e257d5081212b87c2aff05913044fc622c46b4a",
    "assets/example-medallion-dark.html": "de936de0ee480c4fe9d789f576e1f9bbbc69613c903b73435879f5cbf02cb23e",
    "assets/example-medallion-full.html": "8d75d30cb7ae0d3a5479a929d0b288b8ec8cc9072e1ed167d68e97c64321b376",
    "assets/example-medallion.html": "ccd63d89878af1f9d1bcc83e126ea11254f4bbfedb3d87a21e7242793cb2c526",
    "assets/example-nested-dark.html": "8c9862a5a41d2fc5485b51cb9aab318595ceadd2f799ccab7b57e3183906c4c5",
    "assets/example-nested-full.html": "2b87e484fee759346562080dc7639549176af7998389cb0a8be7303649246494",
    "assets/example-nested.html": "fd4001be8af64a8aeae2c9b46e6f476030fcd8791ea3f9b508a503fc5bc70ffb",
    "assets/example-org-chart-dark.html": "2cb9f912a9ab635fe72924425a23aabb3ddfcbc704e6fdbc12cd0399b2d1de5f",
    "assets/example-org-chart-full.html": "f74b14ed6e30a7cf8bcdc8e78dd97c7549d6c73187dea81a13c06edb6e6b1d78",
    "assets/example-org-chart.html": "82356766f5d5af0c10fa60a728c784674138c45416933c15f58d5553a7f4b9b4",
    "assets/example-paved-road-animated.html": "a17f220a610f0616a1d416bde05cb8591182293ac6cd25e3746eaaf08663fc19",
    "assets/example-polar-dark.html": "7c284696cfed61e832dd4dde814840901967cca64bd54a4cddfff7cbeaddb04e",
    "assets/example-polar-full.html": "be8080fa08a05dd27191d3a26585d1246153f9fbdcd5122533833ae57eb016b0",
    "assets/example-polar.html": "3bbfe08f63c9be96cecfdb7432b8236d2f0788bf6008e69254cbbef18cd3fc39",
    "assets/example-policy-trace-animated.html": "1303da75c366e6013dadbc4be0126ab9db34ed0c7a2fdae507c9bd449e871307",
    "assets/example-process-dark.html": "eb0a12c31ab57cce1f300e03c40aedb6d1a2d035320901688b12f32a3805475d",
    "assets/example-process-full.html": "801c93a1cde612566800cf6a07dd77ce5c030d4d065153946bdb84d2d88b8bf8",
    "assets/example-process.html": "7c336a00d6a63fbebd2f9055af8df1b421f25a209900aa70c4028cd747982fb5",
    "assets/example-pyramid-dark.html": "831bc6531d0b3b0eba1b348722a0b3e4d5548f287f5380ddb7e26d3f5edcb80c",
    "assets/example-pyramid-full.html": "ca4c4c9a61072c25ec6e3446c8247f201b89d781d3d2000783fb7a4d50680e1f",
    "assets/example-pyramid.html": "a49c1dd8f932ea82253c7fbbec54365cb722ae65fba975a15c2aa392c27c5fbf",
    "assets/example-quadrant-consultant.html": "0eff4b878e56a0ca3104457128254b1c5b329dc7ed6f891c10807063ccdfb983",
    "assets/example-quadrant-dark.html": "ac1edf5d9c1251a51a93eb82db17fc1820811f1934ec59c1272ea7f89c501465",
    "assets/example-quadrant-full.html": "b4182d3f570e7379b0124667a3268b41f704541d6c6b2e44a4bede954b851457",
    "assets/example-quadrant.html": "95f6100d6059a773bcce44d42a9eedba925226c65cacf6613b8488330ae09934",
    "assets/example-queue-animated.html": "826566166454ba86fafd1731f6e591bbdbae0cb6bb49f5968222c49660d5535f",
    "assets/example-radar-dark.html": "e24eabbc722e67b83ac498407247e1c09d162ff19e047944a323d44594a68258",
    "assets/example-radar-full.html": "5a95adc1d24f5f02b0e5f2c27d901b8c221f50d5586da0e387cc58ecbf34976b",
    "assets/example-radar.html": "9572164b5aa0d8d1e0e713e8ffb7ef750d0b04e06d3eb842829fa4bdaaaff2c1",
    "assets/example-requirement-traceability-dark.html": "57d580a3afc4d55b417c75ec74bb515823f7fe852151f757c6e4d870a83c742d",
    "assets/example-requirement-traceability-full.html": "add40cda3a230d2f46a0f8e0b84a993505dd1221a0fe198cf996e8558205016d",
    "assets/example-requirement-traceability.html": "2714f14ef1b15264a566997ae523b46ca0c13a4f2cc145817f43eb78ae56de39",
    "assets/example-ridgeline-dark.html": "b430c4ec58ab69c044cba2eb39e20adbc8769cbd85fb5f41d8c3f75136d62f90",
    "assets/example-ridgeline-full.html": "33fd98b39d5316ca4b65a65c8cd331c55d032ae5d7de3c94feb5e506168718b9",
    "assets/example-ridgeline.html": "8c6a17edea0742642bfa991ba353c414d2e7608fff09c073d52c3f9de2d71337",
    "assets/example-sankey-dark.html": "4c2a4ff17cfba1412aee8b6569e76c1d314d9ce64d6038c99e89505225b9baf1",
    "assets/example-sankey-full.html": "33f52288399db22c20374ecbfd26ec597b77f3512c03115cea240ece21485bb9",
    "assets/example-sankey.html": "5997eca7d06b41cc779abed904ef1b782a5d9be160f9dffcb0fef067142b904f",
    "assets/example-sbgn-dark.html": "66a7bd8d24698ac6be39b5446ccfcf85b30febaa1624e4f2d494428be377de10",
    "assets/example-sbgn-full.html": "9d9abbea9421019070d088212cc05760b69b739213315b97f4dece24732ef410",
    "assets/example-sbgn.html": "58fb8b36be1a47d0bcf9a0eaefd4e9eabb3988f69024a184ec740726bc483253",
    "assets/example-scatter-dark.html": "347bea032f65f2698f1ce0fe2a5fc01b02dfa03e4fadd84c7a4260369d95fb80",
    "assets/example-scatter-full.html": "af03bf90e91b1a4449ee5b776f08df07a40dec1c1fa27457dc75540c8fa4e379",
    "assets/example-scatter.html": "baa3fe5115e6a0448fd90629c20729b78eb735d5d95b74501f8d3d0fd8183980",
    "assets/example-schedule-network-dark.html": "af2895af046fb61946facf400f83985c9238f998fbfb8beed6b71a3fda4d4f2e",
    "assets/example-schedule-network-full.html": "2ef5c8e630d839c40323772f0299acc01e70d1a3086c2d29522d4b0bd2981a1e",
    "assets/example-schedule-network.html": "b5694bbc7a480455d4059c7e839127d2fc3f08d7dd0ffdee225c443b4d5fe7dd",
    "assets/example-sequence-dark.html": "f2c0fc2e127bce07c78ff09e6b8540f4993d1d85deafbca73af4834b8944e89b",
    "assets/example-sequence-full.html": "8e891b0498e318431dbf0a87c7e5a15d4ab51ff513cfea1fc7a71a68642143c9",
    "assets/example-sequence-oauth-dark.html": "5d4755a698aa868126b51049445d3468a7b40401e902a80319a62a31a7969e64",
    "assets/example-sequence-oauth-full.html": "f067c6bce636a823ac0aaa66c035bb31d75f793f77fb36729110fd9287213fe9",
    "assets/example-sequence-oauth.html": "40b38df11cb54fe055c223a44ddaa7363a2ec0c030dc995e7951a1fb8df42083",
    "assets/example-sequence.html": "aac9bfcad5a001206567a577e9816e3d0904bb3e1afc9d8505fb576b93292db8",
    "assets/example-service-blueprint-dark.html": "b09196833e457a760a435bbee90d21d09525b42ea467e0c0484b8573eb67f6bb",
    "assets/example-service-blueprint-full.html": "23a36032d1f4ed031c1bd353a03504e4a53b29a766f2020f9619949f3fd67f53",
    "assets/example-service-blueprint.html": "e7c29fa4e09c5a7cff1ec75ee2310e3f1d623f4df80854dc2d72a2dd87c31c87",
    "assets/example-slopegraph-dark.html": "36cdffff3d70fa34b091dd0e7814a8892cc6c3436525c666402d790cbbdc5ecc",
    "assets/example-slopegraph-full.html": "1815f1854f486c5163780f2d8f9cf9c0b96a7e42594099dfb31bd14c453a1f55",
    "assets/example-slopegraph.html": "c20f22a1ba7ae6388d3fae506927242173475f6447da655a96f06f92adfd706e",
    "assets/example-state-dark.html": "d5a29f22ee80fef6fe6f857e767fb0bf4afca8bc8f8cbb478f33286d76f88706",
    "assets/example-state-full.html": "683febd8bf1c1658f52f44829d2e72e73453484b54d36409737961718fa2a83c",
    "assets/example-state-lifecycle-dark.html": "caf933ffcfffd7cc46e4354d5d3dd4d2c0ea8fc5c56e5fefb9b0ec63dc3358d9",
    "assets/example-state-lifecycle-full.html": "6b354ce8290c458d3fdce5d30f8f759c8879c9ca490c115156ff6e746c4d3cc2",
    "assets/example-state-lifecycle.html": "0c8406d87facec01143bc4356d896a3ffdc7c429ae481e7ee9fbcd06bfae674c",
    "assets/example-state.html": "33a210ded8261c3117222a7d897a17ccddae89267c4779f19eeaf868a5545a15",
    "assets/example-steps-dark.html": "8b843dc4b13dab50ee21655c3fda409a391e8b2c4e57a9e1e677a1388d2c6bcc",
    "assets/example-steps-full.html": "7b61dc17af1da242c6ddbb3957b592975a400482b359cb7649355ac82f77cda5",
    "assets/example-steps.html": "86c1a6acba504c9d04237c5a66d94dce01ef64ec4f89edca16a5fa8a74f6f14d",
    "assets/example-story-map-dark.html": "0c288216307ff36b43b513445e0e63fa83ed5902695ead17fdd507a470acc6b7",
    "assets/example-story-map-full.html": "fd3a8394c161f8db01c51eb8c3e89b3e0e6fbc85da45c221820dc4ff18036362",
    "assets/example-story-map.html": "2e8765e83ee8fb3c62bd31105d3a73b9f11400035036466d14ec59874e194dde",
    "assets/example-streamgraph-dark.html": "986d4485111c165a18f0eb86055aa326f932c618d26c32f90d6b9457f9189515",
    "assets/example-streamgraph-full.html": "dbc513480b04e07056c6ca0532017ea56b107c278eb70360868fa484b762aedc",
    "assets/example-streamgraph.html": "92f45dca6ce38436d1a790424ec1212b4b5eed74a1a309f85fa037c68facbff5",
    "assets/example-swimlane-dark.html": "d7038fab163c5fc5f56b58502a0d1e07d2961d08a6f6cd10a729864d670186de",
    "assets/example-swimlane-full.html": "dc7bf931bb2ee07072f0fe1e151b0b39a79e0da0317836f897c46b5d2a88953d",
    "assets/example-swimlane.html": "c044be167127091b9bc442fdfe7d1dea439a7de23ea2c9819fb8382e511bb6e9",
    "assets/example-timeline-dark.html": "fb9a45991b281e7937e8288abbfeb6eb12e0140ee5dcac17821721d5129fb647",
    "assets/example-timeline-full.html": "03b38d6dc44286113cf6680ece546affa53ff13092118fb8b4a68b671f55069f",
    "assets/example-timeline.html": "d853c86bfd40491d5b747a07ca10b9d55d3349701ca01f508d83ba972b805788",
    "assets/example-tree-block-decomposition-dark.html": "1a862a84bb85391a850e6c6cc5d657dd019a1c2a4efe8e7d05f6045b876856df",
    "assets/example-tree-block-decomposition-full.html": "9c315f8dcb3693c6c79e9057198e13cb6bd10eb2faa6ed2a5a1956f489271543",
    "assets/example-tree-block-decomposition.html": "c5f3051ea93495e6b040d25642ca7a5e67664678bb5e3147509404ed068551da",
    "assets/example-tree-dark.html": "43aa056d0761d323cad0bd6205de3083fe7413af4e10639cad5e92c8ed41beac",
    "assets/example-tree-full.html": "ee52773ac71a12d584fbe33569da0a64481e05c94ac1ab4729653552e631d8cc",
    "assets/example-tree.html": "6812d3e99c21ddc29d346cfb3713ea997bd6ac1fcb5b29b5c764c200afa0ea20",
    "assets/example-treemap-dark.html": "43cbbb2ec7c30a71edf5f5436e51dd8369cedb1da80f6e6241b62278ea4e5698",
    "assets/example-treemap-full.html": "9339c9007d81969f6d04c30edcf9d3ef558f753ecf9cd8f401978551cfc5c069",
    "assets/example-treemap.html": "224c33a048dc64cbbd687bd826a3a09c8178dcd3d311ea3b53bc43f767f420f6",
    "assets/example-uml-class-dark.html": "eca2e26603714d4df494532a2a712101321a484cc2d1263f7629b8f0e214357d",
    "assets/example-uml-class-full.html": "0c73c3f1b9b4dd569d264a0caff859bf0a3a82849432294c73fed8435a4772e7",
    "assets/example-uml-class.html": "98e58c2833cc6b4f2b3e176bbf173907e7168aedf5310cb900d7bdfeb6e22c8d",
    "assets/example-unit-grid-dark.html": "5d7accc0bfe99114f1ada56883406d25bf5db9fc5ea8792a45e11ca16ea8cbb6",
    "assets/example-unit-grid-full.html": "29edee8fd8e0a05475dc44af632e101fbb840fda3ce6fe751d814f64b3322fea",
    "assets/example-unit-grid.html": "a09af380f38271521a32d5f0959a440d736071d0a96ebf97586d19e2c96c83e0",
    "assets/example-venn-dark.html": "ea604fc7ff3c2da573bba856b54b0ac6a95491f26cb707caefda94ac64215a4f",
    "assets/example-venn-full.html": "7dc6a440cc8881f70f6184200e3557a7501d21f93495a5aa209c6c8c479dd0ba",
    "assets/example-venn.html": "a9f6ab1f15906f7618a2f876bc9cd998a1b0be9b31b7e49eeaf42c3c156340f6",
    "assets/example-wardley-dark.html": "80aff4e268d3775541eca4cf1c1cac918f0895637cd79568d4895e84b9f2046b",
    "assets/example-wardley-full.html": "1986784529ddb529a3d321e6dbc2add1046abccba5fd8bcab23679742731769d",
    "assets/example-wardley.html": "a386727c65063f36df75e096f963c305ca540799c5005daf079ff05e05428436",
    "assets/example-waterfall-dark.html": "ce4eb6038b09b87eca88b6981a7b43d19f603f480b6e91fb16d5d7c58a9103a6",
    "assets/example-waterfall-full.html": "5a5987e9988cad66b26f769e07eca805796895a951a8cc084f0e0aa8503fca09",
    "assets/example-waterfall.html": "501231921ae5065423f75efa6a37fbfc4753ef76d26b9ab116902dc9964ad818",
    "assets/icons.html": "8301219558a40abce2d739def01feda6a8b72adce00f8d60154c989dfb581090",
    "assets/index.html": "934f9c3278efe136519f0fc67a538bb479cc473efc82d3e9ecdc6bf7d9a27476",
    "assets/template-dark.html": "98428c8de2c4fe8e799d7110606421effb876e2e788f8639140854c1033d82d5",
    "assets/template-full.html": "bfe0aa003eb264f4a2b6f10c540d9d7a53950574ed0f5dba2af3cac61fc2f52a",
    "assets/template-motion.html": "0dc228e58e5810fe99d80b0895515bb9a7f129ced1de2960d343f1e9539d5359",
    "assets/template-terminal.html": "d449b50f439214cef9025b91f7ad4d8f786c0f329496aa95b5ea864c1586708d",
    "assets/template.html": "f6978a9d50dd286f32ab149bcf505261b9fc331df7320071f87509a285dee7f4",
    "references/animation.md": "f68388e400f8e11968c7f69ea4c980fe8c01df384b17bddc9e5bf47e6e5eff67",
    "references/doctor.md": "3df848b2431ea9cacc0898ef774c92d58dd7c2e6da26f474ea18d0266e445ff8",
    "references/export-registry.md": "6d35bdccf32e7a2f28ebafac75d099451881a3ad9e268798c86acea2c2c66410",
    "references/export.md": "356aae225112e81a22c3bda90a6c3dfd9ace1c987ec3f02bd01441cabc184266",
    "references/import-drawio.md": "55e340657f7c2f54c9be2349b4b71786779e4ae5d89fb4c1ce4f31de5e49ec08",
    "references/import-excalidraw.md": "323260ca813c3ee5c196362d6424779ee1d3cfcc1afb23329f60d59674a3aeec",
    "references/import-mermaid.md": "90afc8a43511f9e2f92f7347b13b31145f14d35f55e25dd9a2e2687a55c91473",
    "references/import-plantuml.md": "12b98f00c25fa417489e8ae6a9daf2e4accc8c2450d2f1ed3511fcb55567a3ed",
    "references/layout-budget.md": "daa613c1d7e1f6fc59664587869f4114d47a6a9f8e4ee299a25e4360e7faefb6",
    "references/onboarding.md": "b420037953cfca24d406db1589f1ec28bc3b518c651dbb28caef5a20fd499276",
    "references/output-spec.md": "12dc0eed3514e387328651652604ef4fba1a76bce1823a79f4da2993336d1e69",
    "references/primitive-annotation.md": "c4cab11c4660375856a8bea668922b07932199dc26a695ebcf95c5a23ba03ec5",
    "references/primitive-icons.md": "ea768a2b2f169ff3cd98ed41da9ad3a30ed92374bc2da44a8ba83f1f3d453c43",
    "references/primitive-sketchy.md": "8859f0d70c10f46f59817cb348346e7fb9e1609b70a4a513d297b8c850c866a4",
    "references/primitive-terminal.md": "7b52c2fb229c822a60b0061caa64ae6a68aacd4f1c22a1a98d1d0eaaa2333b55",
    "references/primitives-core.md": "601305baed49217870dda15a0ebc879a6a560608cb63fe2108aaebee1abefbc9",
    "references/profiles.md": "8afea09015a456b218287f08a2e9ac44bb50f6a9ebd2a7c1487bd774e89f9016",
    "references/provenance.md": "50346d546b9044bb223f2e1c5b32a85a2b02afed6c1135ddd177fe3291f24f0e",
    "references/semantic-patterns.md": "be3e828fbbf0479f2cd651dc08413481ba695eb9f249a5cf9af72b7860e364db",
    "references/setup.md": "809f5c2b49b077ec7201daa401547e26ee5177cda8b3da9d49a2cf7d85e58378",
    "references/style-guide.md": "320881ec802004384c09ce4f4f087b9242d926b08071d6b908160e14c707d155",
    "references/type-architecture-delta.md": "e5813f26e1fb924863efe70db36f112e1b9570e47335d7f6fa6e46473136e4e5",
    "references/type-architecture.md": "28260c9c0a72fe17ddf6eed7b1fff01c04f58f62bbb7147c45372574c9e38eea",
    "references/type-axonometric-plan.md": "be8ead6d582df5c19fdf611f7540c058f166929293155ab40ddc3ef524232ba6",
    "references/type-bar.md": "0e4d2c7b1df4b1c7a1c47c27db1d298f810bc73f4eb30186eda9827518d38f5b",
    "references/type-data-flow.md": "ad1cd8358c9360663200f5100a199e57e43a4e6702982752220ad423127941e8",
    "references/type-db-schema.md": "91f017b8813cfc63d775809d18659971d0aa5982967af94d47def31690713083",
    "references/type-dependency.md": "1ed31b9888c79533e42da4b5ba5bf3ddad71fc843fb6beab797a99456cb64c08",
    "references/type-deployment.md": "296adfee79069e8fd8f9a19012cca731c5cc237990a0274ca1a8a807173c9fec",
    "references/type-dp-integration.md": "b84195582b3daa1139dced192253ba97dd6984cfd7ba9a0da76a44588f744119",
    "references/type-dp-security-matrix.md": "209f4870ec19d90eff1ab80ecfe0062f3a5075c3b666b1a3a900a27260ba8832",
    "references/type-er.md": "d1495abeb6f5004bd89fface17d3767ebab71c8450dca195b055e18bf3132c57",
    "references/type-event-modeling.md": "b0d8d8a5ba2064cedde94db16c01986e72ac2a22536270635a59710cf6591a76",
    "references/type-exploded.md": "785b904ce1a1be806824c97a5719578a2c32c931fb424d0a1a69c4480a527152",
    "references/type-fishbone.md": "3441d3c73334813bf55cf1d0d96ea1aa4f9e46a60001ba83dfe9442be1745f8b",
    "references/type-flowchart.md": "c2af5e2b849255ae4859125db7b101b74bfb9b201204725c1e83fac51a98ebab",
    "references/type-gantt.md": "3580a844aadd48d36e5190485fb9a2f369f592a26184eadb964eb916dbc0e42a",
    "references/type-heatmap.md": "9ea18de9d461abd8afddef34c7658812ea7f2b22e45fbc3b03caa1099765966a",
    "references/type-high-level.md": "f9629c9b3dd4b85da3a19c762d0f5fd58213b5e3994ad783b2033f4e83260264",
    "references/type-it-state.md": "b5c35f1703a53e3ca4196352912898e5ea5f1fce054a40d4a3568629535cd7ec",
    "references/type-journey.md": "85be7b12d841aec1638d67ad9a599d313a9d42300e35af675a87a0a3e67d9b6f",
    "references/type-kanban.md": "447a8a231d5bb1e822945a02e8bd4adc219b0791bb0182cab48680fbbd88d045",
    "references/type-layers.md": "a822afe4e06ffaf9793f5466810e2504c020e6ae3abd0b9e53c6f7b1368f2609",
    "references/type-line.md": "f29a97ab0e72b23365304dfda6640503e37244eaad2c3851069585a569814089",
    "references/type-loop.md": "9ac996dfa83f41064477f10b61b6bdd2b0ceaefa6053b87432554668adf22af6",
    "references/type-medallion.md": "a1af03521adb53431766a559e05c984ee07871fd3cf495cf63146999f56f6f42",
    "references/type-nested.md": "c16da375df52f047748c65276f564a1b0d7d2dd420170b92dbf7cdac68981516",
    "references/type-org-chart.md": "fd64716f3f419f41785c40fbabb96b36cfddcdfd0cc7ee444585f3e2b528f9c9",
    "references/type-polar.md": "11237fa0be82c3c6e963bc1aaed20283d839c7570dadfd0805e202ea129edba0",
    "references/type-process.md": "cefb9669074ecbc7cd4c78dccb941db1ae52b5bbdc5f20b66edcdf05ea7e2928",
    "references/type-pyramid.md": "c21ef0c6f3832eb30f0cd1aef0e0ec72b6758abbb1b8128acf36e81384679714",
    "references/type-quadrant.md": "eb7d542ddac72e2e1a75cb7ca64ddb67901283859413a133a332137e7fb9e5b1",
    "references/type-radar.md": "49c66e7921e1fd7575cf879852c41aa86e0db7f98b0c8105e3103202af49f563",
    "references/type-requirement-traceability.md": "7e4861050a1a3edb93bdc1f05c2fd8578186bfe29e24158b93de580cc90720eb",
    "references/type-sankey.md": "874866a0867e56525f11f38a11b442b9c33f02f416b632ee76aced7f3bfc2bb5",
    "references/type-sbgn.md": "56de1ca4d3b2a8e3bf9b6b490bbe8165d963875213a67960a1c67cf3bb8036a8",
    "references/type-scatter.md": "e0066ff48cf7af900eea5570abeb060ca8ebbbc60676ac677cfca997c2062b6c",
    "references/type-schedule-network.md": "f4b5dbff04a02377b8ba90a9a4b00a3421bb014e89c157e6623c8b7a0cb9ea76",
    "references/type-sequence.md": "e3a109d4983a951ff670346c352529e48619c1e81db1774edfa6f05d3e93f778",
    "references/type-service-blueprint.md": "ae0475dc5972273d3ff2ab0bf53ae9947e8e35f59decef85f4422459c60c64ca",
    "references/type-state.md": "9c8ed85762d5bbb3672907bc1664ebf94bcc72850efbacf33d5ee12731053122",
    "references/type-steps.md": "2eb15d75d99d0ef37659c417a2730194cae7804f320953cd04096aa6fc0e6c23",
    "references/type-story-map.md": "0ab4fae3de1f9909e20f27ca30414c5574fd8af583c28e1f55ba2af1b50f51fc",
    "references/type-swimlane.md": "3557f11a03e5660e4e44e767caba91a4b8c35892d9aa920967b4387708bcf9fb",
    "references/type-timeline.md": "a6b4ad26c05957835705229579f8c733b32791de9d01f9f268fea8a70228f501",
    "references/type-tree.md": "60194950ef4e46725d7670d93e405a7d4b9af44bf775c549b8f3ce63ca6ce15c",
    "references/type-treemap.md": "7c80b1aa7f3fff205ec74261d874971f5bb09324e3cd357d58c0214acdbbf2de",
    "references/type-uml-class.md": "2940353d4c0afeb25b8d5e830e3408d5fdec3c4c89504739f5d847e064ad12c2",
    "references/type-unit-grid.md": "f27f319d8d68348adcf99221f9c3e54bfca6fa2c9cf20c4afab5222719b26eca",
    "references/type-venn.md": "7ead49ed70f1b2506beb83e9c84862d7dbc63f1225f0e50ecc6e2b1b4a632b38",
    "references/type-wardley.md": "4060402f648fa2ec858850f532675f52ac5d5df0b209c9c9450cc3df332114fb",
    "references/type-waterfall.md": "07db1d30ce52356884b9c7005ad473434c6104257eee0252e3487209e59d0da9",
    "references/upstream-compatibility.md": "fafeac758c2f5ccce50c622ab0bba6c4119d0d1b6225c7233ce15a4ad6d1eb39",
    "scripts/drawio_extract.py": "328e683a2d536a15a45ea8dfc1887bd62f9f1195910f21384dfed6206ae1f7c7",
    "scripts/excalidraw_extract.py": "58f7284b6ee4c1d98d3ec5d7b59221ed273ef2efe76b34ac386de2d194fc087b",
    "scripts/export_png.py": "430ddcc2d39441808bd4217fbdeb944dbb6de0be281782705a81747986d7d348",
    "scripts/export_svg.py": "b5f45b8a36138874e095e07d22c3eaa2322a53927616c8eec5861ddbe9e89d2e",
    "scripts/mermaid_extract.py": "5788098ca6fcbe329b42ff279d2e22e90303ee4850e3489619d746d84b6444ac",
    "scripts/plantuml_extract.py": "d4c2fe72ed59b1f046aeea88adad7f2d94da7471e25ce2b616323f00cf61863c",
    "scripts/self_check.py": "94055febf79eff9bfef42b4fc2635ad83f35fffeb798985fa8477c0bc8e133c5",
    "scripts/verify_geometry.py": "e87c22d2720bfe354b595940d2cf93b555fb5176c823ed3ea46c31a68a10ffd3",
}


class SuperDiagramDesignPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")

    def test_frontmatter_matches_the_hub_contract(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("super-diagram-design", name.group(1).strip())
        description = re.search(r'^description:\s*"(.+)"$', self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1)), 1024)
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)

    def test_vendored_files_match_the_pinned_bytes(self) -> None:
        for relative, expected in PINNED_SHA256.items():
            data = (SKILL_DIR / relative).read_bytes()
            self.assertEqual(expected, hashlib.sha256(data).hexdigest(), relative)

    def test_package_file_whitelist_is_exhaustive(self) -> None:
        shipped = sorted(
            p.relative_to(SKILL_DIR).as_posix() for p in SKILL_DIR.rglob("*") if p.is_file()
        )
        self.assertEqual(len(PINNED_SHA256), len(shipped))
        self.assertEqual(set(PINNED_SHA256), set(shipped))

    def test_license_copy_is_retained(self) -> None:
        retained = (ROOT / "LICENSES" / "Diagram-Design-MIT.txt").read_bytes()
        self.assertEqual(UPSTREAM_LICENSE_SHA256, hashlib.sha256(retained).hexdigest())
        self.assertIn("Copyright (c) 2025 Cathryn Lavery", retained.decode("utf-8"))
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Cathryn Lavery", notices)
        self.assertIn("Diagram-Design-MIT.txt", notices)
        bundled = (SKILL_DIR / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
        self.assertIn("Tabler Icons", bundled)

    def test_gate_registration(self) -> None:
        self.assertIn("skills/super-diagram-design/SKILL.md", INSTALLABLE_SKILL_PATHS)
        self.assertIn("skills/super-diagram-design/SKILL.md", SKILL_BRAND_CONTRACTS)

    def test_packaged_self_check_runs_on_the_standard_library(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "self_check.py"), "--help"],
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(b"self-check", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
