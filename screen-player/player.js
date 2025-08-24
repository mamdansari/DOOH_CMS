const urlParams = new URLSearchParams(window.location.search);
const screenId = urlParams.get('screen_id');
const videoExtensions = ['mp4', 'webm', 'ogg'];

let playlist = [];
let groupId = null;
let currentPlaylistHash = null;
console.log("🆔 screenId = ", screenId);



async function loadPlaylist() {
  const res = await fetch(`/api/playlist/${screenId}`);
  const data = await res.json();
  console.log("Playlist data:", data);

  playlist = data.playlist;
  groupId = data.group_id;
  currentPlaylistHash = data.hash;  // ✅ Save initial hash

  if (groupId) {
    const syncRes = await fetch(`/api/group-time/${groupId}`);
    const syncData = await syncRes.json();
    const syncSeconds = syncData.sync_position_ms / 1000;
    startPlayback(syncSeconds);
  } else {
    startPlayback(0);
  }
}


function startPlayback(syncPosition) {
  const player = document.getElementById('player');

  if (!playlist || playlist.length === 0) {
    console.error("Playlist is empty or undefined. Cannot start playback.");
    player.innerHTML = '<p class="text-red-600">No content available.</p>';
    return;
  }

  // Calculate total duration with safety fallback
  const durations = playlist.map(item => {
    const d = Number(item?.duration);
    if (!isNaN(d) && d > 0) return d;
    // Fallbacks if duration not provided
    if (!item || !item.filename) return 5;
    return /\.(mp4|webm|ogg)$/i.test(item.filename) ? 10 : 5;
    });

  const totalDuration = durations.reduce((a, b) => a + b, 0);
  if (totalDuration === 0) {
    console.error("Total playlist duration is zero, cannot start playback.");
    player.innerHTML = '<p class="text-red-600">Playlist has zero duration.</p>';
    return;
  }

  // Wrap position within totalDuration
  let timeOffset = syncPosition % totalDuration;

  // Find which item to play based on offset
  let index = 0;
  while (index < durations.length && timeOffset >= durations[index]) {
    timeOffset -= durations[index];
    index++;
  }
  if (index >= playlist.length) index = 0;

  playItem(index, timeOffset);
}

function playItem(index, offset = 0) {
  if (!playlist?.length) {
    console.error("Playlist is empty. Cannot play item.");
    return;
  }

  const item = playlist[index];
  if (!item?.filename) {
    console.error("Playlist item missing or filename undefined at index", index);
    return;
  }

  const player = document.getElementById('player');
  const ext = item.filename.split('.').pop().toLowerCase();
  const isVideo = ['mp4', 'webm', 'ogg'].includes(ext);

  // duration assigned by the server (fallback: 10 s for video, 5 s for image)
  const assigned = Number(item.duration) > 0
      ? Number(item.duration)
      : (isVideo ? 10 : 5);

  const remaining = Math.max(0.1, assigned - offset);   // seconds still to play
  player.innerHTML = '';                                // clear previous content

  if (isVideo) {
    const video = document.createElement('video');
    video.src = `/uploads/${item.filename}`;
    video.autoplay = true;
    video.muted = true;
    video.style.width = '100%';
    video.style.height = '100%';
    player.appendChild(video);

    // jump to the correct offset for group sync
    video.addEventListener('loadedmetadata', () => {
      video.currentTime = offset;
    });

    // advance immediately if the file ends early
    video.addEventListener('ended', () => {
      playItem((index + 1) % playlist.length, 0);
    });

    // force-advance after the assigned window
    setTimeout(() => {
      playItem((index + 1) % playlist.length, 0);
    }, remaining * 1000);

  } else { // IMAGE
    const img = document.createElement('img');
    img.src = `/uploads/${item.filename}`;
    img.style.width = '100%';
    img.style.height = '100%';
    player.appendChild(img);

    setTimeout(() => {
      playItem((index + 1) % playlist.length, 0);
    }, remaining * 1000);
  }
}




async function captureSnapshot() {
  const canvas = document.getElementById('snapshotCanvas');
  const player = document.getElementById('player');
  const video = player.querySelector('video');
  const img = player.querySelector('img');

  let width, height;
  const ctx = canvas.getContext('2d');

  if (video && !video.paused && !video.ended) {
    width = video.videoWidth;
    height = video.videoHeight;
    canvas.width = width;
    canvas.height = height;
    ctx.drawImage(video, 0, 0, width, height);
  } else if (img) {
    width = img.naturalWidth || player.clientWidth;
    height = img.naturalHeight || player.clientHeight;
    canvas.width = width;
    canvas.height = height;
    ctx.drawImage(img, 0, 0, width, height);
  } else {
    console.warn("No visible media to capture snapshot from");
    return;
  }

  canvas.toBlob(async function(blob) {
    if (!blob) {
      console.error("Failed to get snapshot blob");
      return;
    }

    try {
      const formData = new FormData();
      formData.append('screen_id', screenId);
      formData.append('snapshot', blob, 'snapshot.png');

      const response = await fetch('/api/snapshot', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        console.error("Snapshot upload failed", response.statusText);
      } else {
        console.log("✅ Snapshot uploaded");
      }
    } catch (error) {
      console.error("Snapshot upload error", error);
    }
  }, 'image/png');
}


async function checkPlaylistUpdate() {
  const res = await fetch(`/api/playlist/${screenId}`);
  const data = await res.json();

  if (data.hash !== currentPlaylistHash) {
    console.log("🔄 Playlist changed, reloading...");

    playlist = data.playlist;
    groupId = data.group_id;
    currentPlaylistHash = data.hash;

    // Re-sync from current position
    if (groupId) {
      const syncRes = await fetch(`/api/group-time/${groupId}`);
      const syncData = await syncRes.json();
      const syncSeconds = syncData.sync_position_ms / 1000;
      startPlayback(syncSeconds);
    } else {
      startPlayback(0);
    }
  }
}

async function pollScreenFlags() {
  try {
    const res = await fetch(`/api/screen-flags/${screenId}`);
    if (!res.ok) {
      console.warn("Failed to fetch screen flags");
      return;
    }
    const flags = await res.json();

    if (flags.force_snapshot) {
      console.log("Manual snapshot flag detected, capturing snapshot...");
      await captureSnapshot();

      // Clear snapshot flag on server
      await fetch('/api/clear-snapshot-flag', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({screen_id: screenId})
      });
    }

    if (flags.force_resync) {
      console.log("Manual resync flag detected, reloading playlist...");
      await loadPlaylist();

      // Clear resync flag on server
      await fetch('/api/clear-sync-flag', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({screen_id: screenId})
      });
    }
  } catch (err) {
    console.error("Error polling screen flags:", err);
  }
}


loadPlaylist().then(pollScreenFlags); // Load playlist, then start flag polling

// Block all touches and gestures
document.addEventListener('touchstart', e => e.preventDefault(), { passive: false });
document.addEventListener('touchmove', e => e.preventDefault(), { passive: false });
document.addEventListener('touchend', e => e.preventDefault(), { passive: false });


setInterval(() => {
  fetch('/api/ping', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ screen_id: screenId })
  })
  .then(res => {
    if (!res.ok) throw new Error("Ping failed");
    return res.json();
  })
  .then(data => console.log("📡 Ping sent", data))
  .catch(err => console.error("Ping error:", err));
}, 15 * 60 * 1000); // every 15 minutes

let tapCount = 0;
let lastTapTime = 0;

document.getElementById('touch-blocker').addEventListener('click', () => {
  const now = Date.now();
  if (now - lastTapTime < 3000) {
    tapCount++;
  } else {
    tapCount = 1;
  }
  lastTapTime = now;

  if (tapCount >= 5) {
    document.getElementById('admin-modal').style.display = 'block';
    document.getElementById('touch-blocker').style.display = 'none';
    console.log("🔓 Admin mode unlocked");
  }
});

function resumePlayback() {
  document.getElementById('admin-modal').style.display = 'none';
  document.getElementById('touch-blocker').style.display = 'block';
  tapCount = 0;
}

document.getElementById('touch-blocker').addEventListener('click', () => {
  console.log('Blocker clicked!');
});

document.addEventListener('DOMContentLoaded', () => {
  const fsOverlay = document.createElement('div');
  fsOverlay.style.position = 'fixed';
  fsOverlay.style.top = '0';
  fsOverlay.style.left = '0';
  fsOverlay.style.width = '100vw';
  fsOverlay.style.height = '100vh';
  fsOverlay.style.zIndex = '9999';
  fsOverlay.style.background = 'transparent';
  fsOverlay.style.cursor = 'pointer';

  fsOverlay.addEventListener('click', () => {
    const elem = document.documentElement;
    if (elem.requestFullscreen) {
      elem.requestFullscreen();
    } else if (elem.webkitRequestFullscreen) {
      elem.webkitRequestFullscreen();
    } else if (elem.msRequestFullscreen) {
      elem.msRequestFullscreen();
    }
    fsOverlay.remove();
  });

  document.body.appendChild(fsOverlay);
});


setInterval(captureSnapshot, 50 * 60 * 1000); // every 50 minutes
setInterval(checkPlaylistUpdate, 300000);     // every 5 minutes
setInterval(pollScreenFlags, 30000);          // every 30 seconds


