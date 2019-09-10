using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// A simple place holder which indicats that this item may be part of the sanbox creator suite.
/// It allows more control over this item, especially when rewinding or resetting the playback, 
/// then this will be used to avoid restarting any of its animators, audio or particle systems.
/// </summary>
public class SandboxItemChild : MonoBehaviour {
	//placeholder script.
}

public class SandboxBase : MonoBehaviour
{
	protected virtual void Awake()
    {
		foreach (var child in gameObject.GetComponentsInChildren<Transform>(true)) { //place a SandboxItemChild on all transforms so scripts know this is a sandbox item, prevents it from being rewond and stuff..
			if (child.gameObject.GetComponent<SandboxItemChild> ()==null) { //only need one, incase something already added one to this object
				child.gameObject.AddComponent<SandboxItemChild> ();
			}
		}
    }
			
}
