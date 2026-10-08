// Live task status, shared by everyone through Cloud Firestore (Firebase project pc5253-progress).
// Each task's status is one document, tasks/<task id> = { status: "todo" | "doing" | "done" }.
// Firebase loads in the background; until it answers, or if it cannot be reached, pages show the
// status written in data/project.js. Access rules: firestore.rules at the repository root.

(function () {
  "use strict";

  const Team = window.Team;
  const SDK = "https://www.gstatic.com/firebasejs/12.19.0/";
  // A Firebase web config only identifies the project; it is not a secret. firestore.rules limits writes.
  const CONFIG = {
    apiKey: "AIzaSyB-0TcuZBijTSsn8grocX7vDAw9mnFsCVM",
    authDomain: "pc5253-progress.firebaseapp.com",
    projectId: "pc5253-progress",
    storageBucket: "pc5253-progress.firebasestorage.app",
    messagingSenderId: "694616374380",
    appId: "1:694616374380:web:03eb722dcf84ce9b25ac49"
  };

  Promise.all([import(SDK + "firebase-app.js"), import(SDK + "firebase-firestore.js")])
    .then(([appSdk, fs]) => {
      const db = fs.getFirestore(appSdk.initializeApp(CONFIG));
      const tasks = fs.collection(db, "tasks");
      const save = (id, status) => fs.setDoc(fs.doc(tasks, id), { status });
      fs.onSnapshot(tasks,
        (snap) => {
          const map = {};
          snap.forEach((d) => { map[d.id] = d.data().status; });
          Team.setLive(map);
          Team.setSync("live", save);
        },
        (err) => { console.warn("[live] Firestore unavailable:", err); Team.setSync("offline", null); });
    })
    .catch((err) => { console.warn("[live] Firebase SDK failed to load:", err); Team.setSync("offline", null); });
})();
