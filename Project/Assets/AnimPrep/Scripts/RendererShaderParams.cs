using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;
using System.Linq;

#if UNITY_EDITOR
using UnityEditor;

[CustomEditor(typeof(RendererShaderParams))]
class RendererShaderParamsEditor : Editor {
	public override void OnInspectorGUI() {

		RendererShaderParams myScript = (RendererShaderParams)target;
		if (GUILayout.Button ("Store Parameters")) {
			myScript.StoreParams ();
		}
		if (GUILayout.Button ("ret")) {
			myScript.runtest (myScript);
		}
		DrawDefaultInspector ();
	}


}
#endif
public class RendererShaderParams : MonoBehaviour {


	/// <summary>
	/// Because unity assetbundles and standard shaders do not automatically take into account the 
	/// currently set keyword, this must be done manually. This script stores the keywords that were
	/// present at the time the character was created and represend the shader's behavior for the renderer
	/// which this component is attached to.
	/// </summary>
	/// <value>The shader keyword parameters.</value>





	public struct MakehumanRenderer {
		public Renderer renderer;
		public MakehumanMeshBoneType type;
	}


	public enum MakehumanMeshBoneType {
		none,
		eyeballs,
		eyelashes,
		eyebrows,
		teeth,
		tongue		
	}


	public void runtest (RendererShaderParams myScript) {

		var animator = myScript.GetComponentInParent<Animator> ();
		var childrenRenderers = animator.GetComponentsInChildren<Renderer> ();

		//ArmatureLinker linker = animator.transform.GetComponentInChildren<ArmatureLinker> ();

		MakehumanRenderer[] makehumanRenderers = new MakehumanRenderer[childrenRenderers.Length];


		List<string> bonesList = new List<string> ();

		//foreach (Renderer renderer in childrenRenderers) {

		Debug.Log (childrenRenderers.Length);

		for (int i = 0; i < childrenRenderers.Length; i++) {
			Renderer renderer = childrenRenderers [i];

			makehumanRenderers [i] = new MakehumanRenderer {
				renderer = renderer,
				type = MakehumanMeshBoneType.none
			};


			var skinnedRenderer = renderer.GetComponent<SkinnedMeshRenderer> ();
			if (skinnedRenderer == null) {
				continue;
			}

			var weights = skinnedRenderer.sharedMesh.boneWeights;
			//var allBones = skinnedRenderer.bones;

			bonesList.Clear ();

			foreach (var weight in weights) {
				var bIdx = weight.boneIndex0;
				var bTran = skinnedRenderer.bones [bIdx];

				if (!bonesList.Contains (bTran.name)) {
					bonesList.Add (bTran.name);
					//Debug.Log (bTran.name);
				}
			}


			if (bonesList.Count == 2 &&
				new string[] {
					"eye.R",
					"eye.L"
				}.All (n => bonesList.Contains (n))) {
				//Debug.Log ("I THINK THIS IS AN EYE");
				makehumanRenderers [i].type = MakehumanMeshBoneType.eyeballs;
				continue;
			}


			if (bonesList.Count == 5 &&
				new string[] {
					"head",
					"orbicularis03.R",
					"orbicularis03.L",
					"orbicularis04.R",
					"orbicularis04.L"
				}.All (n => bonesList.Contains (n))) {
				//Debug.Log ("I THINK THIS IS AN EYELASH");
				makehumanRenderers [i].type = MakehumanMeshBoneType.eyelashes;
				continue;
			}


			if (bonesList.Count == 3 &&
				new string[] {
					"head",
					"oculi01.R",
					"oculi01.L"
				}.All (n => bonesList.Contains (n))) {
				//Debug.Log ("I THINK THIS IS AN EYEBROW");
				makehumanRenderers [i].type = MakehumanMeshBoneType.eyebrows;
				continue;
			}


			if (bonesList.Count == 2 &&
				new string[] {
					"jaw",
					"head"
				}.All (n => bonesList.Contains (n))) {
				//Debug.Log ("I THINK THIS IS TEETH");
				makehumanRenderers [i].type = MakehumanMeshBoneType.teeth;
				continue;
			}


			if (bonesList.Count == 10 &&
				new string[] {
					"tongue07.R",
					"tongue04",
					"tongue07.L",
					"tongue03",
					"tongue06.L",
					"tongue05.L",
					"tongue02",
					"tongue01",
					"tongue06.R",
					"tongue05.R",
				}.All (n => bonesList.Contains (n))) {
				//Debug.Log ("I THINK THIS IS A TONGUE");
				makehumanRenderers [i].type = MakehumanMeshBoneType.tongue;
				continue;
			}

		}



		foreach (MakehumanRenderer makehumanRenderer in makehumanRenderers) {
			var renderer = makehumanRenderer.renderer;

			if (renderer != null) {
				renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
				renderer.receiveShadows = true;

				var material = renderer.sharedMaterial;

				var mainColor = material.GetColor ("_Color");
				mainColor.a = 1.0f; //always do this, just because unity is weird and seemingly random alpha values always appear
				material.SetColor ("_Color", mainColor);



				if (makehumanRenderer.type != MakehumanMeshBoneType.none) {
					renderer.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
					renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
				

					switch (makehumanRenderer.type) {
					case MakehumanMeshBoneType.eyeballs:					
						break;
					case MakehumanMeshBoneType.eyebrows:
					case MakehumanMeshBoneType.eyelashes:
						material.shader = Shader.Find ("Sprites/Default");				
						break;
					case MakehumanMeshBoneType.teeth:
					case MakehumanMeshBoneType.tongue:
						//if (renderer.GetComponent<SkinnedMeshRenderer> ()) {
						//	renderer.GetComponent<SkinnedMeshRenderer> ().updateWhenOffscreen = false;
						//}
						break;
					}


				}




			}


		}
	}
























	public static void StoreAllRenderers(GameObject go) {

		foreach (var renderer in go.GetComponentsInChildren<Renderer>()) {
			if (renderer.GetComponent<RendererShaderParams> ()) {
				renderer.GetComponent<RendererShaderParams> ().StoreParams ();
			} else {
				renderer.gameObject.AddComponent<RendererShaderParams> ().StoreParams();
			}
		}

	}



	[Serializable]
	public struct MaterialParams {
		public Material material;

		public int renderQueue;

		public ShaderKeywordParams[] shaderKeywordParams;
		public ShaderValuesParams[] shaderValuesParams;
	}

	public MaterialParams[] materialsParams;

	[Serializable]
	public struct ShaderKeywordParams {
		public string key;
		public bool value;
	}
	[Serializable]
	public struct ShaderValuesParams {
		public string key;
		public float value;
	}

	static string[] keywordsBoolean = new string[] {
		"_SPECGLOSSMAP",
		"_METALLICGLOSSMAP",
		"_EMISSION",
		"_ALPHATEST_ON",
		"_ALPHABLEND_ON",
		"_ALPHAPREMULTIPLY_ON",
		"LIGHTPROBE_SH",
		"DIRECTIONAL",
		"SHADOWS_SCREEN",
		"VERTEXLIGHT_ON",
		"POINT",
		"SPOT",
		"POINT_COOKIE",
		"DIRECTIONAL_COOKIE",
		"SHADOWS_DEPTH",
		"SHADOWS_CUBE",
	};


	static string[] keywordsFloats = new string[] {
		"_SrcBlend",
		"_DstBlend",
		"_Cull",
		"_ZWrite",
		"_Cutoff",
		"_Glossiness",
		"_GlossMapScale",
		"_ZTest"
	};


	public void StoreParams() {

		var mats = GetComponent<Renderer> ().sharedMaterials;
		materialsParams = new MaterialParams[mats.Length];

		for (int n = 0; n < mats.Length; n++) {
			var mat = mats[n];
			if (mat == null) {
				continue; //maybe it was missing?
			}

			List<ShaderKeywordParams> shaderKeywordParamsList = new List<ShaderKeywordParams> ();
			for (int i = 0; i < keywordsBoolean.Length; i++) {


				var keyword = keywordsBoolean [i];
				shaderKeywordParamsList.Add ( new ShaderKeywordParams () {
				//materialsParams[n].shaderKeywordParams [i] = new ShaderKeywordParams () {
					key = keyword,
					value = mat.IsKeywordEnabled (keyword),
				});
			}

			List<ShaderValuesParams> shaderValuesParamsList = new List<ShaderValuesParams> ();
			for (int i = 0; i < keywordsFloats.Length; i++) {
				var keyword = keywordsFloats [i];
				if (!mat.HasProperty (keyword)) {
					continue;//might be hair or a different shader than standard
				}
				shaderValuesParamsList.Add ( new ShaderValuesParams () {
				//materialsParams[n].shaderValuesParams [i] = new ShaderValuesParams () {
					key = keyword,
					value = mat.GetFloat (keyword),
				});
			}

			//mat.renderQueue = 3000;

			materialsParams[n] = new MaterialParams () { 
				material = mat,

				renderQueue = mat.renderQueue,

				shaderKeywordParams = shaderKeywordParamsList.ToArray (),// new ShaderKeywordParams[keywordsBoolean.Length],
				shaderValuesParams = shaderValuesParamsList.ToArray (),// new ShaderValuesParams[keywordsFloats.Length],
			};

		}
	}




}
