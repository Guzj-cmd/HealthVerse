# Spatial experience — 2026-11-26

Reference: https://lusion.co/ — interaction and scene direction only; no proprietary code or assets copied.

The entire viewport is a Three.js world with physically lit arches, floating objects, floor and camera parallax. Accessible HTML navigation and functional panels form translucent foreground surfaces. Sense, body and design views share a detailed workspace rendered through the same WebGL renderer. View changes move the background camera continuously; panel hover gives subtle depth, with motion pause and reduced-motion support.

Workspace: orbit drag, front/side/reset camera controls, raycast selection of monitor/chair/cup, height slider and before/after layout preview. The avatar and scene are conceptual illustrations, not reconstruction of a user. Camera/video analysis and model evidence remain separate real inputs. No health metrics are generated from the decorative scene.

## Assets

- Three.js 0.170.0, MIT; license at assets/vendor/three/LICENSE. Dependencies are served locally.
- Current student avatar: Microsoft Rocketbox Male_Child_01 facial FBX with original face/body color and normal textures, MIT. Source https://github.com/microsoft/Microsoft-Rocketbox/tree/master/Assets/Avatars/Children/Male_Child_01 . License in assets/models/ROCKETBOX-LICENSE.md. The author names this asset Child; it is used as a youthful student illustration, not as a verified age or body-size reference. Scale is purely illustrative. Replaced adult after audience clarified as adolescents.
- Previous detailed adult avatar: Microsoft Rocketbox Male_Adult_04, converted GLB from https://github.com/927tanmay/react-ai-voice-avatar , MIT; retained unused as iteration asset.
- First iteration used Cesium Man ©2017 Cesium, CC BY 4.0, https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CesiumMan . Replaced after user requested more facial and clothing detail; original GLB retained as unused iteration asset.
- Desk, monitor, chair, keyboard, cup, spatial architecture: project-authored procedural 3D geometry.

All newly downloaded dependencies and the original model were staged in D:/CodexData/HealthVerse/spatial-assets before copying runtime assets into the application.

## Iterations

1. Existing dream background: output/playwright/healthverse-dream-background.png.
2. Whole-page WebGL scene and illustrated mesh: output/playwright/spatial-fullpage-v1.png.
3. Lower exposure and richer blue layers: output/playwright/spatial-fullpage-blue.png.
4. Detailed textured human, human close-up/top-view controls, and centered memory graph labels. Graph defect was missing text-anchor:middle in the active stylesheet.
5. User clarified adolescent audience: student avatar, book/pencil, youth-oriented learning-space heading. Richer dragging, evidence picking and calibrated reach-volume interactions remain proposed enhancements, not claimed as implemented.

## Verification

- WAR built and deployed to local Tomcat (HTTP page and model resources load).
- Browser reports student model loaded, no resource HTTP errors and zero console errors/warnings.
- Exercised human close-up, navigation, plan B, and original-layout toggle.
- Memory graph: all five labels use text-anchor middle and their x positions equal circle cx.
- Desktop 1512×982 and mobile 390×844 checked; mobile document has no horizontal overflow.
- Current screenshots: output/playwright/spatial-student-final.png, spatial-student-closeup.png, spatial-memory-aligned.png, spatial-mobile.png.
- Camera permission and real-video inference were not re-exercised in this visual-only verification; existing input handlers were preserved.
