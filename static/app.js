document.addEventListener("DOMContentLoaded", () => {
  const timeline = document.getElementById("timeline");
  const refreshBtn = document.getElementById("refresh-btn");
  const themeToggleBtn = document.getElementById("theme-toggle");
  const shareBtn = document.getElementById("share-btn");
  const exportBtn = document.getElementById("export-btn");
  const spinner = document.getElementById("spinner");
  const messageContainer = document.getElementById("message-container");

  let releasesData = [];
  let selectedIndex = -1;
  let lastFetchTime = 0;
  const DEBOUNCE_INTERVAL_MS = 2000; // 2 seconds rate limit

  // Load and apply saved theme
  const savedTheme = localStorage.getItem("theme") || "light";
  if (savedTheme === "dark") {
    document.body.classList.add("dark-theme");
  }

  // Theme toggle
  themeToggleBtn.addEventListener("click", () => {
    document.body.classList.toggle("dark-theme");
    const currentTheme = document.body.classList.contains("dark-theme") ? "dark" : "light";
    localStorage.setItem("theme", currentTheme);
    // Apply styling updates to active elements if needed
    updateTimelineThemeClasses();
  });

  function updateTimelineThemeClasses() {
    const items = document.querySelectorAll(".release-item");
    items.forEach(item => {
      if (document.body.classList.contains("dark-theme")) {
        item.classList.add("dark-item");
      } else {
        item.classList.remove("dark-item");
      }
    });
  }

  // Fetch releases
  async function fetchReleases() {
    const now = Date.now();
    if (now - lastFetchTime < DEBOUNCE_INTERVAL_MS) {
      console.warn("Refresh rate limited");
      return;
    }
    lastFetchTime = now;

    spinner.classList.remove("hidden");
    timeline.innerHTML = "";
    messageContainer.textContent = "";
    shareBtn.disabled = true;
    selectedIndex = -1;

    try {
      const response = await fetch("/api/releases");
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      releasesData = await response.json();
      renderReleases(releasesData);
    } catch (error) {
      console.error("Failed to fetch releases:", error);
      messageContainer.textContent = "Error loading release notes. Please try again later.";
      // If we already have items (from cached data rendered previously), keep them or show error.
      if (releasesData.length === 0) {
        timeline.innerHTML = "";
      }
    } finally {
      spinner.classList.add("hidden");
    }
  }

  function stripHtml(html) {
    if (!html) return "";
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return doc.body.textContent || "";
  }

  function renderReleases(releases) {
    if (!releases || releases.length === 0) {
      messageContainer.textContent = "No releases found";
      return;
    }

    releases.forEach((release, index) => {
      const item = document.createElement("div");
      item.className = "release-item";
      if (document.body.classList.contains("dark-theme")) {
        item.classList.add("dark-item");
      }
      
      const headerDiv = document.createElement("div");
      headerDiv.className = "release-header";

      const title = document.createElement("h3");
      title.className = "release-title";
      title.textContent = release.title || "Untitled Release";

      const copyBtn = document.createElement("button");
      copyBtn.className = "copy-card-btn";
      copyBtn.textContent = "Copy";
      copyBtn.addEventListener("click", (e) => {
        e.stopPropagation(); // Prevent card selection toggle
        
        const plainDesc = stripHtml(release.description || "");
        const textToCopy = `Title: ${release.title || ""}\nDate: ${release.pubDate ? new Date(release.pubDate).toLocaleDateString() : "Unknown"}\nLink: ${release.link || ""}\n\nDescription:\n${plainDesc}`;
        
        navigator.clipboard.writeText(textToCopy).then(() => {
          copyBtn.textContent = "Copied!";
          setTimeout(() => {
            copyBtn.textContent = "Copy";
          }, 1500);
        }).catch(err => {
          console.error("Could not copy text: ", err);
        });
      });

      headerDiv.appendChild(title);
      headerDiv.appendChild(copyBtn);

      const date = document.createElement("div");
      date.className = "release-date";
      date.textContent = release.pubDate ? new Date(release.pubDate).toLocaleDateString() : "Unknown date";

      const desc = document.createElement("div");
      desc.className = "release-description";
      // We strip HTML tags when displaying description in the UI or let innerHTML show it (but we strip for Twitter sharing)
      desc.innerHTML = release.description || "";

      item.appendChild(headerDiv);
      item.appendChild(date);
      item.appendChild(desc);

      item.addEventListener("click", () => {
        toggleSelection(index);
      });

      timeline.appendChild(item);
    });
  }

  function toggleSelection(index) {
    const items = document.querySelectorAll(".release-item");
    if (selectedIndex === index) {
      // Clear selection
      items[selectedIndex].classList.remove("selected");
      selectedIndex = -1;
      shareBtn.disabled = true;
    } else {
      // Select new item
      if (selectedIndex !== -1 && items[selectedIndex]) {
        items[selectedIndex].classList.remove("selected");
      }
      selectedIndex = index;
      items[selectedIndex].classList.add("selected");
      shareBtn.disabled = false;
    }
  }

  // Twitter share action
  shareBtn.addEventListener("click", () => {
    if (selectedIndex === -1) {
      console.warn("No item selected to share");
      return;
    }

    const release = releasesData[selectedIndex];
    const rawText = `Google Cloud BigQuery: ${release.title}`;
    const cleanText = stripHtml(rawText);
    const link = release.link || "";

    // Build intent URL with 280 char limit handling
    const tweetText = cleanText.length > 200 ? cleanText.substring(0, 197) + "..." : cleanText;
    const shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}&url=${encodeURIComponent(link)}`;

    window.open(shareUrl, "_blank");
  });

  refreshBtn.addEventListener("click", fetchReleases);

  exportBtn.addEventListener("click", () => {
    if (!releasesData || releasesData.length === 0) {
      alert("No data available to export.");
      return;
    }
    
    // Convert release data to CSV format
    const headers = ["Title", "Link", "Description", "Publish Date"];
    const rows = releasesData.map(release => [
      release.title || "",
      release.link || "",
      stripHtml(release.description || ""),
      release.pubDate || ""
    ]);

    const csvContent = [
      headers.map(h => `"${h.replace(/"/g, '""')}"`).join(","),
      ...rows.map(r => r.map(val => `"${val.replace(/"/g, '""')}"`).join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "bigquery_releases.csv");
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // Initial fetch
  fetchReleases();
});
