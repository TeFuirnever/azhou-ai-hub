# Icon Catalog — vendored excalidraw-libraries

The **complete official library set** (231 libraries, 4134 items) is vendored
gzipped at `references/libraries/` (~10 MB) and resolved offline by
`scripts/excalidraw_lib.py` — `search` / `items` / `merge` / `catalog` never
touch the network for vendored sources. Refresh by re-running the vendor step
from a shallow clone of [excalidraw/excalidraw-libraries](https://github.com/excalidraw/excalidraw-libraries):
`gzip -c libraries/<author>/<name>.excalidrawlib > references/libraries/<author>/<name>.excalidrawlib.gz`.

## Quick pick (verified in practice)

| Entity type | Library | Item (substring for merge) |
|---|---|---|
| Server / node machine | `anna-pastushko/architecture-diagram-components` | `Server` |
| User, user group | `anna-pastushko/architecture-diagram-components` | `User`, `Users` |
| Client device / monitor | `anna-pastushko/architecture-diagram-components` | `Device` |
| Firewall / security appliance | `dwelle/network-topology-icons` | `Firewall` |
| Network client computer | `dwelle/network-topology-icons` | `Client` |
| Kubernetes pod | `boemska-nik/kubernetes-icons` | `pod` |
| Database / storage (GCP-style) | `mguidoti/google-icons` | `Cloud SQL`, `Cloud Storage` |
| AWS service icons | `childishgirl/aws-architecture-icons` | service name |

No official library ships a vetted **gear / robot / AI** icon — draw those from
primitives. Items flagged `[HAS IMAGE]` by `items` embed raster images and will
NOT render through the export pipeline — pick a vector sibling instead.

Merge calibration (from production use): `--scale 1.0–1.3` for a 50–70px icon;
`--strip-text` when the scene already labels the node; `--roughness 1` to match
a hand-drawn scene; the merge output prints the art-only bbox — fit niches to
that, not to the pre-strip bbox.

## Full inventory (auto-generated)

`★` = broadest everyday usefulness. `imgs` = count of image-based items (won't render).

| Library | Items | imgs | |
|---|---|---|---|
| `7demonsrising/azure-compute.excalidrawlib` | 17 |  |
| `7demonsrising/azure-containers.excalidrawlib` | 6 |  |
| `7demonsrising/azure-general.excalidrawlib` | 19 |  |
| `7demonsrising/azure-network.excalidrawlib` | 29 |  |
| `7demonsrising/azure-storage.excalidrawlib` | 13 |  |
| `Arqtangeles/architecture.excalidrawlib` | 42 |  |
| `BjoernKW/UML-ER-library.excalidrawlib` | 21 |  |
| `IvanReznikov/yellow-box.excalidrawlib` | 1 |  |
| `Vasudevatirupathinaidu/random-figure-drawings.excalidrawlib` | 15 |  |
| `aarondiel/logic-gates.excalidrawlib` | 7 |  |
| `ad115/music-notation.excalidrawlib` | 23 |  |
| `adamkdean/comms-platform-icons.excalidrawlib` | 6 |  |
| `adrigrana/japanese-pitch-accent-graphs-template-collection.excalidrawlib` | 90 |  |
| `aimpizza/3d-coordinate-systems-graphs.excalidrawlib` | 5 |  |
| `aleksandr-hovhannisyan/clocks.excalidrawlib` | 3 |  |
| `alexandertsukanov/elk-stack.excalidrawlib` | 5 |  |
| `alluvion/montessori-basic-grammar-symbols.excalidrawlib` | 10 |  |
| `amelia/micro.excalidrawlib` | 1 |  |
| `andreandreandradecosta/3d-shapes.excalidrawlib` | 2 |  |
| `anna-pastushko/architecture-diagram-components.excalidrawlib` | 11 |  | ★
| `anumithaapollo12/emojis.excalidrawlib` | 48 |  |
| `aocgame/domainstorytelling.excalidrawlib` | 7 |  |
| `arach/systems-design-components.excalidrawlib` | 6 |  |
| `aretecode/decision-flow-control.excalidrawlib` | 8 |  |
| `aretecode/system-design-template.excalidrawlib` | 8 |  |
| `artem-anufrij-live-de/artem-s-icons.excalidrawlib` | 22 |  |
| `boemska-nik/kubernetes-icons.excalidrawlib` | 74 |  | ★
| `booknerdonmars/bullet-journal-trackers.excalidrawlib` | 2 |  |
| `braweria/customer-journey-map.excalidrawlib` | 14 |  |
| `cengizhanparlak/code-essentials.excalidrawlib` | 2 |  |
| `cespin/domain-driven-design.excalidrawlib` | 16 |  |
| `childishgirl/aws-architecture-icons.excalidrawlib` | 249 |  | ★
| `chuqbach/data-platform.excalidrawlib` | 33 |  |
| `claracavalcante/baby-characters.excalidrawlib` | 4 |  |
| `clementbosc/gcp-icons.excalidrawlib` | 83 |  |
| `cloud/cloud.excalidrawlib` | 19 |  |
| `coexist/mq.excalidrawlib` | 6 |  |
| `corlaez/hexagonal-architecture.excalidrawlib` | 27 |  |
| `damitr/astronomical-symbols.excalidrawlib` | 27 |  |
| `danielpza/barotrauma.excalidrawlib` | 27 |  |
| `danimaniarqsoft/scrum-board.excalidrawlib` | 1 |  |
| `david-prta/dart-and-flutter-icons.excalidrawlib` | 2 |  |
| `dbssticky/data-viz.excalidrawlib` | 32 |  |
| `dday987/common-home-network-basics.excalidrawlib` | 8 |  |
| `demondarakna/dnd-writing-icons-for-dm.excalidrawlib` | 42 |  |
| `devdaejungyoon/github-actions.excalidrawlib` | 4 |  |
| `dhaval_godwani/webpage-frames.excalidrawlib` | 3 |  |
| `dhtoran/stick-people.excalidrawlib` | 7 |  |
| `dimitrios-fkliaras/clouds.excalidrawlib` | 4 |  |
| `dmitry-burnyshev/c4-architecture.excalidrawlib` | 10 |  |
| `dmtwng/archimate-application-layer.excalidrawlib` | 18 |  |
| `dpalay/common-screen-resolutions.excalidrawlib` | 12 |  |
| `drwnio/drwnio.excalidrawlib` | 18 |  |
| `drwnio/storytelling.excalidrawlib` | 16 |  |
| `dwelle/despair.excalidrawlib` | 10 |  |
| `dwelle/hearts.excalidrawlib` | 5 |  |
| `dwelle/network-topology-icons.excalidrawlib` | 10 |  | ★
| `econ-graphs/macroeconomics.excalidrawlib` | 4 |  |
| `egor-romanov/risk-based-test-strategy.excalidrawlib` | 8 |  |
| `eho9734/2022-gantt.excalidrawlib` | 1 |  |
| `ei-au/computers.excalidrawlib` | 4 |  |
| `ella/science-chemistry-gcse.excalidrawlib` | 4 |  |
| `erlina/data-processing.excalidrawlib` | 8 |  |
| `esteevens/logos.excalidrawlib` | 8 |  |
| `esteevens/retail-peripherals.excalidrawlib` | 3 |  |
| `ewels/nextflow-seqera-nf-core.excalidrawlib` | 14 |  |
| `excacomp/mobile-kit.excalidrawlib` | 3 |  |
| `excacomp/web-kit.excalidrawlib` | 9 |  |
| `excalidraw/valentine-s-day.excalidrawlib` | 7 |  |
| `farisology/data-science.excalidrawlib` | 7 |  |
| `ferminrp/awesome-icons.excalidrawlib` | 24 |  |
| `ferminrp/awesome-slides.excalidrawlib` | 16 |  |
| `ferminrp/gantt.excalidrawlib` | 1 |  |
| `ferminrp/post-it.excalidrawlib` | 13 |  |
| `fibreninja/fibre-network.excalidrawlib` | 3 |  |
| `finfin/flow-chart-symbols.excalidrawlib` | 15 |  |
| `fortijosh/fortinet.excalidrawlib` | 33 |  |
| `franky47/apple-devices-frames.excalidrawlib` | 13 |  |
| `fraoustin/bpmn.excalidrawlib` | 34 |  |
| `g-script/android.excalidrawlib` | 9 |  |
| `g-script/charts.excalidrawlib` | 4 |  |
| `g-script/forms.excalidrawlib` | 26 |  |
| `g-script/medias.excalidrawlib` | 6 |  |
| `gabi-as-cosmos/periodic-table.excalidrawlib` | 1 |  |
| `gabrielamacakova/basic-ux-wireframing-elements.excalidrawlib` | 69 |  |
| `gabrielamacakova/christmas-essentials.excalidrawlib` | 27 |  |
| `gabrielamacakova/halloween-elements.excalidrawlib` | 39 |  |
| `gabrielamacakova/presentation-bundle.excalidrawlib` | 20 |  |
| `gianpaima/stick-figures-collaboration.excalidrawlib` | 6 |  |
| `gregory/golang-gophers.excalidrawlib` | 6 |  |
| `h7y/dropdowns.excalidrawlib` | 3 |  |
| `hartmut-co-uk/kafka-streams-topology-design.excalidrawlib` | 72 |  |
| `https-github-com-jinmingyi1998/collective-operation.excalidrawlib` | 8 |  |
| `https-github-com-papacrispy/uml-library-activity-diagram.excalidrawlib` | 16 |  |
| `https-github-com-patrickcuba/snowflake-iconography.excalidrawlib` | 54 |  |
| `https-github-com-sly-dog/ds-visualizations.excalidrawlib` | 2 |  |
| `https-github-com-tomorrowx-dev/tomorrowx-composable-agentic-platform-cap.excalidrawlib` | 4 |  |
| `https-github-com-ytrkptl/math-teacher-library.excalidrawlib` | 12 |  |
| `husainkhambaty/aws-simple-icons.excalidrawlib` | 17 |  |
| `ibex-technology/web3-crypto-solution-design-v1.excalidrawlib` | 10 |  |
| `infamousjoeg/cyberark.excalidrawlib` | 52 |  |
| `intradeus/algorithms-and-data-structures-arrays-matrices-trees.excalidrawlib` | 22 |  |
| `inwardmovement/information-architecture.excalidrawlib` | 17 |  |
| `ipedrazas/go-icons.excalidrawlib` | 2 |  |
| `itsmestefanjay/camunda-platform-icons.excalidrawlib` | 12 |  |
| `jakubpawlina/graphs.excalidrawlib` | 12 |  |
| `jasoncoelho/arduino-micro.excalidrawlib` | 1 |  |
| `jatinkrmalik/atlassian-product-suite.excalidrawlib` | 7 |  |
| `jdelacruz/veeam_unofficial.excalidrawlib` | 76 |  |
| `jgansaown/ultimate-frisbee.excalidrawlib` | 4 |  |
| `jgodoy/network-locations.excalidrawlib` | 5 |  |
| `jgodoy/organization-chart.excalidrawlib` | 9 |  |
| `jgodoy/racks-and-servers-components.excalidrawlib` | 5 |  |
| `jhoughes/veeam.excalidrawlib` | 13 |  |
| `jjadup/mathematical-symbols.excalidrawlib` | 15 |  |
| `jkattnis/traffic-signs.excalidrawlib` | 9 |  |
| `jordangeurtsen/uml-component-diagram.excalidrawlib` | 6 |  |
| `jordangeurtsen/uml-deployment-diagram.excalidrawlib` | 8 |  |
| `jumpingrivers/r.excalidrawlib` | 2 |  |
| `jurgen-kattnis/picasso-s-line-drawings.excalidrawlib` | 9 |  |
| `kabirsinghshekhawat/genealogy-essentials.excalidrawlib` | 12 |  |
| `kaligule/robots.excalidrawlib` | 7 |  |
| `kbentekik/piping-and-instrumentation-diagram-p-id.excalidrawlib` | 28 |  |
| `kinghavok/some-common-cloud-apps.excalidrawlib` | 15 |  |
| `kleinpetr/simple-sticky-notes.excalidrawlib` | 7 |  |
| `krustvalentin/printers.excalidrawlib` | 3 |  |
| `kvchitrapu/data-sources.excalidrawlib` | 6 |  |
| `kvchitrapu/secure_shell.excalidrawlib` | 3 |  |
| `kvmet/chickens.excalidrawlib` | 3 |  |
| `kwirke/some-handdrawn-signs.excalidrawlib` | 2 |  |
| `l8y/music-instruments.excalidrawlib` | 9 |  |
| `lipis/polygons.excalidrawlib` | 6 |  |
| `lipis/stars.excalidrawlib` | 12 |  |
| `lowess/kubernetes-icons-set.excalidrawlib` | 19 |  |
| `lukethorp/databricks-architecture-icons.excalidrawlib` | 24 |  |
| `m47812/office-items.excalidrawlib` | 17 |  |
| `madhusuthanan-b/front-end-tech-and-tools.excalidrawlib` | 6 |  |
| `madhusuthanan-b/html-css-js-icons.excalidrawlib` | 3 |  |
| `maeddes/technology-logos.excalidrawlib` | 18 |  |
| `manuelernestog/universal-ui-kit.excalidrawlib` | 22 |  |
| `marcottebear/raspberrypi-zero.excalidrawlib` | 1 |  |
| `markopolo123/dev_ops.excalidrawlib` | 29 |  |
| `martinberger-ch/oracle-cloud-infrastructure-icons.excalidrawlib` | 35 |  |
| `marwinburesch/github-icons.excalidrawlib` | 7 |  |
| `marwinburesch/html-input-elements.excalidrawlib` | 8 |  |
| `mateuszbaransanok/it-icons.excalidrawlib` | 48 |  |
| `matthijssloep/fair-web-icons.excalidrawlib` | 4 |  |
| `mattias-fjellstrom/hashicorp.excalidrawlib` | 8 |  |
| `mayankguptadotcom/wardley-mapping-canvas.excalidrawlib` | 12 |  |
| `mguidoti/google-icons.excalidrawlib` | 139 |  | ★
| `mguidoti/it-tools-logos.excalidrawlib` | 5 |  |
| `mguidoti/original-google-architecture-icons.excalidrawlib` | 139 |  |
| `michelcaradec/cloud-design-patterns.excalidrawlib` | 24 |  |
| `mikhailredis/redis-grafana.excalidrawlib` | 13 |  |
| `molibden/types-and-values-in-javascript.excalidrawlib` | 11 |  |
| `monty/an-adjustable-arrow-shape-that-can-be-modified-in-a-number-of-ways-to-suit-different-use-cases.excalidrawlib` | 3 |  |
| `moochin/simple-characters.excalidrawlib` | 49 |  |
| `morgemoensch/gadgets.excalidrawlib` | 5 |  |
| `mppowell/circuit-components.excalidrawlib` | 24 |  |
| `mrmaffen/dnd-ttrpg-battle-map-creature-tokens.excalidrawlib` | 1 |  |
| `mwc360/microsoft-fabric-architecture-icons.excalidrawlib` | 135 |  |
| `narhari-motivaras/aws-architecture-icons.excalidrawlib` | 4 |  |
| `nemeki/ttrpg-clocks.excalidrawlib` | 21 |  |
| `newbyca/cryptocurrencies.excalidrawlib` | 11 |  |
| `niknm/systemdesignicons.excalidrawlib` | 3 |  |
| `nikordaris/team-topologies.excalidrawlib` | 8 |  |
| `novakkkarel/nsx-t-vmware.excalidrawlib` | 20 |  |
| `ocapraro/bubbles.excalidrawlib` | 4 |  |
| `odraghi/vmware-architecture-design.excalidrawlib` | 48 |  |
| `oehrlis/db-eng.excalidrawlib` | 39 |  |
| `patrickcuba/data-vault.excalidrawlib` | 30 |  |
| `pclainchard/it-logos.excalidrawlib` | 31 |  |
| `pfound/football-icons.excalidrawlib` | 6 |  |
| `pgilfernandez/basic-shapes.excalidrawlib` | 32 |  |
| `pixelass/body-builder-kit-1.excalidrawlib` | 15 |  |
| `pixelass/character-kit-1.excalidrawlib` | 2 |  |
| `pixelass/female-heads-diverse.excalidrawlib` | 8 |  |
| `pixelass/head-builder-kit-1.excalidrawlib` | 49 |  |
| `pixelass/male-heads-diverse-1.excalidrawlib` | 12 |  |
| `pixelass/tools.excalidrawlib` | 9 |  |
| `pocomane/boardgame.excalidrawlib` | 10 |  |
| `pratheeshpm/basic-system-design.excalidrawlib` | 7 |  |
| `pret/chess-set.excalidrawlib` | 13 |  |
| `r4z4/elixir.excalidrawlib` | 6 |  |
| `revolunet/raspberrypi3.excalidrawlib` | 1 |  |
| `risjain/electrical-engineering.excalidrawlib` | 15 |  |
| `rkjc/arduino-boards.excalidrawlib` | 5 |  |
| `rkjc/schematic-symbols.excalidrawlib` | 24 |  |
| `robin-muller/digital-signal-processing.excalidrawlib` | 8 |  |
| `rochacbruno/computer-parts.excalidrawlib` | 8 |  |
| `rockssk/microsoft-azure-cloud-icons.excalidrawlib` | 19 |  |
| `rohanp/system-design.excalidrawlib` | 24 |  |
| `samu_x86/network-elements.excalidrawlib` | 5 |  |
| `schiriki123/playing-cards.excalidrawlib` | 5 |  |
| `selanas/it-logos.excalidrawlib` | 7 |  |
| `sharathsanketh/biology.excalidrawlib` | 4 |  |
| `shellerbrand/canvases.excalidrawlib` | 2 |  |
| `shinkim/desktop-resolutions.excalidrawlib` | 4 |  |
| `shinkim/presentation-templates.excalidrawlib` | 6 |  |
| `simalexan/wardley-maps-symbols.excalidrawlib` | 10 |  |
| `simonthomine/pathology.excalidrawlib` | 20 |  |
| `sketchingdev/banners.excalidrawlib` | 7 |  |
| `slobodan/aws-serverless.excalidrawlib` | 15 |  |
| `spfr/lo-fi-wireframing-kit.excalidrawlib` | 23 |  |
| `stojanovic/aws-serverless-icons-v2.excalidrawlib` | 24 |  |
| `stuc2010/enterprise-integration-patterns.excalidrawlib` | 42 |  |
| `sudotachy/medicine.excalidrawlib` | 4 |  |
| `surya-teja-venteddu/make-your-calendar.excalidrawlib` | 8 |  |
| `swissarmysam/maps.excalidrawlib` | 4 |  |
| `thebrahmnicboy/Logic-Gates.excalidrawlib` | 10 |  |
| `thijsdev/snowflake.excalidrawlib` | 8 |  |
| `thrsz/organic-chemistry-basics.excalidrawlib` | 27 |  |
| `timothygalvin/excalidraw-archimate-template.excalidrawlib` | 38 |  |
| `toman/checkmarks.excalidrawlib` | 4 |  |
| `tuckdiaz/internet-service-providers.excalidrawlib` | 7 |  |
| `tvoozmagnificent/coordinates.excalidrawlib` | 4 |  |
| `tylerkron/event-storming.excalidrawlib` | 7 |  |
| `ubigene/misc-azure-icons.excalidrawlib` | 7 |  |
| `weareborg/synths-and-fx.excalidrawlib` | 6 |  |
| `webkul/ecommerce-mobile-ui.excalidrawlib` | 75 |  |
| `wictorwilen/microsoft-365-icons.excalidrawlib` | 37 |  |
| `wmartzh/data-flow.excalidrawlib` | 4 |  |
| `xxxdeveloper/icons.excalidrawlib` | 65 |  |
| `xxxdeveloper/system-icons.excalidrawlib` | 24 |  |
| `xxxdeveloper/wireframing-placeholders.excalidrawlib` | 10 |  |
| `youritjang/azure-cloud-services.excalidrawlib` | 19 |  |
| `youritjang/software-architecture.excalidrawlib` | 7 |  |
| `youritjang/stick-figures.excalidrawlib` | 9 |  |
| `yuelfei/deep-learning.excalidrawlib` | 12 |  |
| `zanetworker/red-hat.excalidrawlib` | 3 |  |
| `zesty-lemur/microsoft-apps.excalidrawlib` | 8 |  |
