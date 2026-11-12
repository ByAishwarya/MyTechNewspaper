// read-store.js
// ------------------------------------------------------------------
// WHERE "read" IS SAVED. The rest of the app only calls these three
// functions and never knows where the data lives.
//
// Part 1 (now): saved in this browser (localStorage).
// Part 3 (later): we replace ONLY this file with calls to
//   API Gateway -> Lambda -> DynamoDB. app.js stays unchanged.
//
// The functions are "async" even though localStorage is instant,
// because the DynamoDB version will need to wait for the network.
// Making them async now means app.js won't need changing later.
// ------------------------------------------------------------------

const STORAGE_KEY = "mtn-read-v1";

function loadAll() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch (e) {
    return {}; // private window or blocked storage: start empty
  }
}

function saveAll(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.warn("Could not save read status", e);
  }
}

const ReadStore = {
  // Returns a Set of story IDs the user has read.
  async getReadIds() {
    return new Set(Object.keys(loadAll()));
  },

  // Marks one story as read and remembers when.
  async markRead(storyId) {
    const data = loadAll();
    if (!data[storyId]) {
      data[storyId] = { read_at: new Date().toISOString() };
      saveAll(data);
    }
  },

  // Marks one story as unread again.
  async markUnread(storyId) {
    const data = loadAll();
    delete data[storyId];
    saveAll(data);
  },

  // For testing: forget everything.
  async clear() {
    saveAll({});
  }
};
