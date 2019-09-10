using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System.IO;

#if UNITY_EDITOR
using UnityEditor;

[CustomEditor(typeof(TakeScreenshot))]
class TakeScreenshotEditor : Editor {
	public override void OnInspectorGUI() {
		TakeScreenshot baseScript = (TakeScreenshot)target;
		if(GUILayout.Button("Take Screenshot")) {
			var folder = Path.Combine( Application.dataPath, "Screenshots");
			if (!Directory.Exists (folder)) {
				Directory.CreateDirectory (folder);
			}

			var path = Path.Combine (folder, "screenshot.png");
			Debug.Log (path);
			baseScript.CamCapture(path);
		}

		if(GUILayout.Button("Set Frustum To Scene Object")) {
			baseScript.SetFrustumToSceneObject();
		}

		if(GUILayout.Button("Evaluate Curve")) {
			if (baseScript.t > 1) {
				baseScript.t = 0;
			}

			baseScript.EvaluateCurve(baseScript.m_sceneObject, baseScript.t);
			baseScript.t += 0.025f;
		}
		DrawDefaultInspector ();
	}
}
#endif

[ExecuteInEditMode]
public class TakeScreenshot : MonoBehaviour {

	public Camera m_camera { get {return GetComponent<Camera>();} }

	public Transform m_sceneObject;

	void Update() {
		if (Application.isPlaying) {
			if (t > 1) {
				t = 0;
				dir = !dir;
			}
			EvaluateCurve (m_sceneObject, Mathf.Abs((dir ? 1 : 0) - t ) );
			t += Time.deltaTime * 0.25f;

			SetFrustumToSceneObject();
		}
	}

	//Frustum Bounds Helpers
	public void SetFrustumToSceneObject() {
		SetFrustumToSceneObject (m_sceneObject);
	}

	private Vector3 v3FrontTopLeft;
	private Vector3 v3FrontTopRight;
	private Vector3 v3FrontBottomLeft;
	private Vector3 v3FrontBottomRight;
	private Vector3 v3BackTopLeft;
	private Vector3 v3BackTopRight;
	private Vector3 v3BackBottomLeft;
	private Vector3 v3BackBottomRight;    

	void CalcPositons(Bounds bounds, Transform t){		
		Vector3 v3Center = bounds.center;
		Vector3 v3Extents = bounds.extents;

		v3FrontTopLeft     = new Vector3(v3Center.x - v3Extents.x, v3Center.y + v3Extents.y, v3Center.z - v3Extents.z);  // Front top left corner
		v3FrontTopRight    = new Vector3(v3Center.x + v3Extents.x, v3Center.y + v3Extents.y, v3Center.z - v3Extents.z);  // Front top right corner
		v3FrontBottomLeft  = new Vector3(v3Center.x - v3Extents.x, v3Center.y - v3Extents.y, v3Center.z - v3Extents.z);  // Front bottom left corner
		v3FrontBottomRight = new Vector3(v3Center.x + v3Extents.x, v3Center.y - v3Extents.y, v3Center.z - v3Extents.z);  // Front bottom right corner
		v3BackTopLeft      = new Vector3(v3Center.x - v3Extents.x, v3Center.y + v3Extents.y, v3Center.z + v3Extents.z);  // Back top left corner
		v3BackTopRight     = new Vector3(v3Center.x + v3Extents.x, v3Center.y + v3Extents.y, v3Center.z + v3Extents.z);  // Back top right corner
		v3BackBottomLeft   = new Vector3(v3Center.x - v3Extents.x, v3Center.y - v3Extents.y, v3Center.z + v3Extents.z);  // Back bottom left corner
		v3BackBottomRight  = new Vector3(v3Center.x + v3Extents.x, v3Center.y - v3Extents.y, v3Center.z + v3Extents.z);  // Back bottom right corner

		v3FrontTopLeft     = t.TransformPoint(v3FrontTopLeft);
		v3FrontTopRight    = t.TransformPoint(v3FrontTopRight);
		v3FrontBottomLeft  = t.TransformPoint(v3FrontBottomLeft);
		v3FrontBottomRight = t.TransformPoint(v3FrontBottomRight);
		v3BackTopLeft      = t.TransformPoint(v3BackTopLeft);
		v3BackTopRight     = t.TransformPoint(v3BackTopRight);
		v3BackBottomLeft   = t.TransformPoint(v3BackBottomLeft);
		v3BackBottomRight  = t.TransformPoint(v3BackBottomRight);    
	}

	private static Bounds CalculateLocalBounds(Transform t)	{
		Quaternion currentRotation = t.rotation;
		t.rotation = Quaternion.Euler(0f,0f,0f);
		Bounds bounds = new Bounds(t.position, Vector3.zero);
		foreach(Renderer renderer in t.GetComponentsInChildren<Renderer>())
		{
			bounds.Encapsulate(renderer.bounds);
		}
		Vector3 localCenter = bounds.center - t.position;
		bounds.center = localCenter;
		//Debug.Log("The local bounds of this model is " + bounds);
		t.rotation = currentRotation;

		return bounds;
	}

	Vector3 CalcViewBox(Vector3 center, Vector3 up, Vector3 forward) {
		/*
		Debug.DrawLine (v3FrontTopLeft, v3FrontTopRight, Color.yellow);
		Debug.DrawLine (v3FrontTopRight, v3FrontBottomRight, Color.yellow);
		Debug.DrawLine (v3FrontBottomRight, v3FrontBottomLeft, Color.yellow);
		Debug.DrawLine (v3FrontBottomLeft, v3FrontTopLeft, Color.yellow);
		*/
		/*
		Debug.DrawLine (v3FrontTopLeft, v3BackTopLeft, Color.yellow); //cross member
		Debug.DrawLine (v3FrontTopRight, v3BackTopRight, Color.yellow); //cross member
		Debug.DrawLine (v3FrontBottomRight, v3BackBottomRight, Color.yellow); //cross member
		Debug.DrawLine (v3FrontBottomLeft, v3BackBottomLeft, Color.yellow); //cross member
		*/
		/*
		Debug.DrawLine (v3BackTopLeft, v3BackTopRight, Color.yellow);
		Debug.DrawLine (v3BackTopRight, v3BackBottomRight, Color.yellow);
		Debug.DrawLine (v3BackBottomRight, v3BackBottomLeft, Color.yellow);
		Debug.DrawLine (v3BackBottomLeft, v3BackTopLeft, Color.yellow);
		*/

		var right = Quaternion.Euler (up * 90) * forward; //compute a right vecotr orthagonal to the camera and scene object facing vector

		//Front Top
		var dotXFTL = (Vector3.Dot(right, v3FrontTopLeft - center ) ) ;
		var dotXFTR = (Vector3.Dot(right, v3FrontTopRight - center) ) ;

		var dotYFTL = (Vector3.Dot(up,v3FrontTopLeft - center ) ) ;
		var dotYFTR = (Vector3.Dot(up,v3FrontTopRight - center) ) ;

		var dotZFTL = (Vector3.Dot(forward, v3FrontTopLeft - center ) ) ;
		var dotZFTR = (Vector3.Dot(forward, v3FrontTopRight - center) ) ;

		//Front Bot
		var dotXFBL = (Vector3.Dot(right,v3FrontBottomLeft - center ) ) ;
		var dotXFBR = (Vector3.Dot(right,v3FrontBottomRight - center) ) ;

		var dotYFBL = (Vector3.Dot(up,v3FrontBottomLeft - center ) ) ;
		var dotYFBR = (Vector3.Dot(up,v3FrontBottomRight - center) ) ;

		var dotZFBL = (Vector3.Dot(forward,v3FrontBottomLeft - center ) ) ;
		var dotZFBR = (Vector3.Dot(forward,v3FrontBottomRight - center) ) ;

		//Back Top
		var dotXBTL = (Vector3.Dot(right, v3BackTopLeft - center ) ) ;
		var dotXBTR = (Vector3.Dot(right, v3BackTopRight - center) ) ;

		var dotYBTL = (Vector3.Dot(up, v3BackTopLeft - center ) ) ;
		var dotYBTR = (Vector3.Dot(up, v3BackTopRight - center) ) ;

		var dotZBTL = (Vector3.Dot(forward, v3BackTopLeft - center ) ) ;
		var dotZBTR = (Vector3.Dot(forward, v3BackTopRight - center) ) ;

		//Back Bot
		var dotXBBL = (Vector3.Dot(right,v3BackBottomLeft - center ) ) ;
		var dotXBBR = (Vector3.Dot(right,v3BackBottomRight - center) ) ;

		var dotYBBL = (Vector3.Dot(up,v3BackBottomLeft - center ) ) ;
		var dotYBBR = (Vector3.Dot(up,v3BackBottomRight - center) ) ;

		var dotZBBL = (Vector3.Dot(forward,v3BackBottomLeft - center ) ) ;
		var dotZBBR = (Vector3.Dot(forward,v3BackBottomRight - center) ) ;

		//Find the longest vector for each axis
		var maxX = Mathf.Max (dotXFTL, dotXFTR, dotXFBL, dotXFBR, dotXBTL, dotXBTR, dotXBBL, dotXBBR);
		//Debug.DrawRay(center, right * maxX, Color.red); //draw the ray that lies on the outter most extent for this axis
		var maxY = Mathf.Max (dotYFTL, dotYFTR, dotYFBL, dotYFBR, dotYBTL, dotYBTR, dotYBBL, dotYBBR);
		//Debug.DrawRay(center, up * maxY, Color.green); //draw the ray that lies on the outter most extent for this axis
		var maxZ = Mathf.Max (dotZFTL, dotZFTR, dotZFBL, dotZFBR, dotZBTL, dotZBTR, dotZBBL, dotZBBR);
		//Debug.DrawRay(center, forward * maxZ, Color.blue); //draw the ray that lies on the outter most extent for this axis

		return new Vector3 (maxX, maxY, maxZ); //the vectors local to camera which represent the visible bounds for the rotated object(s)
	}

	public void SetFrustumToSceneObject(Transform sceneObject) {
		var bounds = CalculateLocalBounds (sceneObject);

		Vector3 xyz = bounds.size;
		Vector3 xyzE = bounds.extents;
		Vector3 xyzC = bounds.center;

		var xyzEP = sceneObject.rotation * xyzE;
		var xyzCP = sceneObject.rotation * xyzC;

		var up = m_camera.transform.up;// Quaternion.Euler (Vector3.right * 90) * fwd;
		var fwd = (m_camera.transform.position - xyzCP).normalized;

		CalcPositons(bounds, sceneObject);
		var xyzViewbox = CalcViewBox(xyzCP, up, fwd);
		var xyzP = sceneObject.rotation * xyz;

		var closestDistance = Vector3.Dot(fwd, xyzCP) + xyzViewbox.z; //xyzViewbox.z;// + cam.nearClipPlane;
		var closestPoint =  fwd * closestDistance;// xyzCP + (fwd * closestDistance);

		var farthestDistance = Vector3.Dot(fwd, xyzCP) - xyzViewbox.z; //xyzViewbox.z;// + cam.nearClipPlane;
		var farthestPoint =  fwd * farthestDistance;// xyzCP + (fwd * closestDistance);

		Vector3 refPos = sceneObject.transform.position + fwd * closestDistance;// m_camera.transform.parent.position;

		var xyP = new Vector2 (xyzP.x, xyzP.y);
		var xyCP = new Vector2 (xyzCP.x, xyzCP.y);

		var distanceFromObj = Vector3.Distance(refPos, sceneObject.position) ;

		float distance = Mathf.Max(
			Mathf.Abs(xyzViewbox.x),
			Mathf.Abs(xyzViewbox.y)
		);

		distance /= (distanceFromObj * Mathf.Tan(0.5f * m_camera.fieldOfView * Mathf.Deg2Rad));
		// Move camera in -z-direction; change '1.0f' to your needs
		var newZ = distance * 1f * Mathf.Abs( Vector3.Dot(fwd, refPos) );// 3f;// Mathf.Max(distance * 3f, closestDistance);

		m_camera.transform.position = new Vector3(xyCP.x, xyCP.y, -newZ);
		m_camera.nearClipPlane = 0.1f;// Mathf.Max(Vector3.Distance (m_camera.transform.position, closestPoint) - m_camera.fieldOfView * 0.1f, 0.1f);
		m_camera.farClipPlane = 1000f;// Mathf.Max(Vector3.Distance (m_camera.transform.position, farthestPoint) + m_camera.fieldOfView * 0.1f, 1.0f);

		m_camera.transform.LookAt (xyzCP); //maybe not needed?
	}


	//Camera Capture Helpers
	public AnimationCurve curveX;
	public AnimationCurve curveY;
	public AnimationCurve curveZ;

	[HideInInspector]
	public float t = 0;
	[HideInInspector]
	public bool dir;

	public void EvaluateCurve(Transform sceneObject, float t) {
		var valX = curveX.Evaluate (t) * 90;
		var valY = curveY.Evaluate (t) * 90;
		var valZ = curveZ.Evaluate (t) * 90;
		sceneObject.rotation = Quaternion.Euler (valX,valY,valZ);

		SetFrustumToSceneObject (sceneObject);
	}
		
	public Light directionalLight;

	public Texture2D CamCapture()
	{		
		m_camera.Render();

		Texture2D image = new Texture2D(m_camera.targetTexture.width, m_camera.targetTexture.height);
		image.ReadPixels(new Rect(0, 0, m_camera.targetTexture.width, m_camera.targetTexture.height), 0, 0);
		image.Apply();

		return image;
	}

	public void CamCapture(string destPath)
	{		
		RenderTexture currentRT = RenderTexture.active;
		RenderTexture.active = m_camera.targetTexture;

		Texture2D image = CamCapture ();

		image.ReadPixels(new Rect(0, 0, m_camera.targetTexture.width, m_camera.targetTexture.height), 0, 0);
		image.Apply();

		RenderTexture.active = currentRT;

		var Bytes = image.EncodeToPNG();
		DestroyImmediate(image);

		var destDir = Path.GetDirectoryName (destPath);
		if (!Directory.Exists (destDir)) {
			Directory.CreateDirectory (destDir);
		}
		File.WriteAllBytes(destPath, Bytes);
	}
}


