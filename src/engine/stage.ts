// The Stage (K2-01, D-104): her VRM bust-up, from Yuri's shell (github.com/
// YatharthJorwal/Yuri, src/main.ts boot(), the author's own code). An imperative
// three.js module outside React: `createStage` owns the renderer, the scene and one
// animation loop that drives idle motion, eyes, expression life and lip-sync from
// the other files in this folder. React only mounts the canvas and passes hooks.

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";

import { ExpressionLife, blendTarget } from "./expression-life";
import { BlinkController, GazeController, addHeadFollow, mulberry32, type GazeFrame } from "./eyes";
import { lookAtHeight } from "./framing";
import { IDLE_BONE_NAMES, applyIdleOffsets, idleOffsets } from "./idle-motion";
import { getMouthOpenValue, getSpeechProgress } from "./lipsync";

// Yuri's framing, offsets from her own head bone, so any VRM frames itself (FR-ST-2).
const FOV = 32;
const DISTANCE = 1.2;
const HEIGHT_OVER_HEAD = 0.05;
const HEADROOM = 0.05;
const MAX_RISE = 0.2;

const EMOTIONS = ["happy", "angry", "sad", "teasing", "surprised", "neutral"] as const;
type Emotion = (typeof EMOTIONS)[number];
const PRESETS = ["happy", "angry", "sad", "relaxed", "surprised", "neutral"] as const;
type Preset = (typeof PRESETS)[number];
// Yuri's blends: "teasing" has no VRM preset, so relaxed with a touch of angry;
// happy capped at 0.8 (VRoid's Joy over-squeezes at full weight).
const BLENDS: Record<Emotion, Partial<Record<Preset, number>>> = {
  happy: { happy: 0.8 },
  angry: { angry: 0.8 },
  sad: { sad: 1 },
  teasing: { relaxed: 1, sad: 0.05, angry: 0.05 },
  surprised: { surprised: 1 },
  neutral: { neutral: 1 },
};
const BLEND_SPEED = 4;   // per second

export interface StageHooks {
  /** A turn is running or she is speaking: expression life holds her mood. */
  busy(): boolean;
  /** The picture viewer (D-104): the user turns and zooms her with the mouse. */
  orbit?: boolean;
}

export type Framing = "bust" | "full";

export interface Stage {
  /** A finished reply's emotion tag (FR-ST-7); unknown names are ignored. */
  setEmotion(emotion: string | null | undefined): void;
  /** Bust-up (the Stage) or her whole body (the picture viewer). */
  frame(framing: Framing): void;
  /** A PNG of what is on screen now, with a see-through background. */
  capture(): Promise<Blob | null>;
  dispose(): void;
}

/** Arms down from the T-pose (Yuri's values, measured on a real VRM). */
function restPose(vrm: VRM): void {
  const h = vrm.humanoid;
  h?.getNormalizedBoneNode("leftUpperArm")?.rotation.set(0, 0, -1.35);
  h?.getNormalizedBoneNode("rightUpperArm")?.rotation.set(0, 0, 1.35);
  h?.getNormalizedBoneNode("leftLowerArm")?.rotation.set(0, -0.15, 0);
  h?.getNormalizedBoneNode("rightLowerArm")?.rotation.set(0, 0.15, 0);
}

/** Loads the VRM at `url` into `canvas` and starts her loop. Rejects when the model
 * cannot be loaded (the caller shows FR-ST-5's panel). */
export async function createStage(canvas: HTMLCanvasElement, url: string, hooks: StageHooks): Promise<Stage> {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 20);
  // Flat, front-on light: MToon's hard bands go blotchy under a steep key light.
  const key = new THREE.DirectionalLight(0xffffff, 0.9);
  key.position.set(0, 1.6, 2.2);
  scene.add(key, new THREE.HemisphereLight(0xffffff, 0xd8d8e0, 1.1));

  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  let vrm: VRM;
  try {
    const gltf = await loader.loadAsync(url);
    vrm = gltf.userData.vrm as VRM;
    if (!vrm) throw new Error("not a VRM");
  } catch (err) {
    renderer.forceContextLoss();   // the browser caps live WebGL contexts; release it now
    renderer.dispose();
    throw err;
  }
  VRMUtils.rotateVRM0(vrm);
  VRMUtils.combineSkeletons(vrm.scene);
  VRMUtils.combineMorphs(vrm);
  restPose(vrm);
  scene.add(vrm.scene);

  vrm.scene.updateMatrixWorld(true);
  const head = new THREE.Vector3(0, 1.4, 0);
  vrm.humanoid?.getNormalizedBoneNode("head")?.getWorldPosition(head);
  const top = new THREE.Box3().setFromObject(vrm.scene, true).max.y;
  const box = new THREE.Box3().setFromObject(vrm.scene, true);
  const controls = hooks.orbit ? new OrbitControls(camera, canvas) : null;
  if (controls) {
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.minDistance = 0.4;
    controls.maxDistance = 6;
  }
  const frameAs = (framing: Framing) => {
    const target = new THREE.Vector3();
    if (framing === "bust") {
      const lookY = lookAtHeight(head.y, top, { distance: DISTANCE, fovDegrees: FOV, headroom: HEADROOM, maxRise: MAX_RISE });
      target.set(head.x, lookY, head.z);
      camera.position.set(head.x, lookY + HEIGHT_OVER_HEAD, head.z + DISTANCE);
    } else {
      // Her whole height in the frame, with a little room round her.
      const height = box.max.y - box.min.y;
      const distance = (height * 0.58) / Math.tan(THREE.MathUtils.degToRad(FOV / 2));
      target.set(head.x, box.min.y + height / 2, head.z);
      camera.position.set(head.x, target.y, head.z + distance);
    }
    camera.lookAt(target);
    controls?.target.copy(target);
    controls?.update();
  };
  frameAs("bust");

  const fit = () => {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w === 0 || h === 0) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  const resize = new ResizeObserver(fit);
  resize.observe(canvas);
  fit();

  const idleBones = Object.fromEntries(IDLE_BONE_NAMES.map((n) => [n, vrm.humanoid?.getNormalizedBoneNode(n) ?? null]));
  const rng = mulberry32((Math.random() * 0xffffffff) >>> 0);
  const gaze = new GazeController(rng);
  const blinker = new BlinkController(rng);
  const life = new ExpressionLife(mulberry32((Math.random() * 0xffffffff) >>> 0));
  const weights: Record<Preset, number> = { happy: 0, angry: 0, sad: 0, relaxed: 0, surprised: 0, neutral: 1 };
  let gazeFrame: GazeFrame = { yaw: 0, pitch: 0, headYaw: 0, headPitch: 0 };
  let idleTime = 0;
  let raf = 0;
  const clock = new THREE.Clock();

  const animate = () => {
    raf = requestAnimationFrame(animate);
    const dt = Math.min(0.1, clock.getDelta());
    const speaking = getSpeechProgress() !== null;
    gazeFrame = gaze.update(dt, speaking);
    if (gaze.consumeBlinkRequest()) blinker.requestBlink();
    const em = vrm.expressionManager;
    em?.setValue("blink", blinker.update(dt, speaking));
    if (vrm.lookAt) {
      vrm.lookAt.yaw = gazeFrame.yaw;
      vrm.lookAt.pitch = gazeFrame.pitch;
    }
    if (em) {
      const step = Math.min(1, BLEND_SPEED * dt);
      const targets = blendTarget(BLENDS, life.update(dt, hooks.busy() || speaking), PRESETS);
      for (const p of PRESETS) {
        weights[p] += (targets[p] - weights[p]) * step;
        em.setValue(p, weights[p]);
      }
      em.setValue("aa", getMouthOpenValue());
    }
    idleTime += dt;
    applyIdleOffsets(idleBones, idleOffsets(idleTime));
    addHeadFollow(idleBones, gazeFrame);
    vrm.update(dt);
    controls?.update();
    renderer.render(scene, camera);
  };
  animate();

  return {
    setEmotion(emotion) {
      if (emotion && (EMOTIONS as readonly string[]).includes(emotion)) life.set(emotion);
    },
    frame: frameAs,
    capture() {
      // toBlob copies the canvas as it is now, before the browser clears it.
      renderer.render(scene, camera);
      return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    },
    dispose() {
      cancelAnimationFrame(raf);
      controls?.dispose();
      resize.disconnect();
      scene.remove(vrm.scene);
      VRMUtils.deepDispose(vrm.scene);
      renderer.forceContextLoss();   // the browser caps live WebGL contexts; release it now
      renderer.dispose();
    },
  };
}
