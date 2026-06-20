const telegram = window.Telegram && window.Telegram.WebApp;
if (telegram) {
  telegram.ready();
  telegram.expand();
}

const form = document.querySelector("#new-game-form");
const statusElement = document.querySelector("#status");
const button = form.querySelector("button");
const token = new URLSearchParams(window.location.search).get("token") || "";
const apiBaseUrl = (window.CHIPS_BOT_API_BASE_URL || window.location.origin).replace(/\/$/, "");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  statusElement.textContent = "Starting game...";

  const data = new FormData(form);
  const payload = {
    token,
    init_data: telegram ? telegram.initData : "",
    chip_value_sgd: String(data.get("chip_value_sgd") || ""),
    host_commission_percent: String(data.get("host_commission_percent") || ""),
    buy_in_mode: String(data.get("buy_in_mode") || "SGD"),
  };

  try {
    const response = await fetch(`${apiBaseUrl}/api/new-game`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || "Unable to start game.");
    }
    statusElement.textContent = `Game #${result.game_id} started.`;
    if (telegram) {
      setTimeout(() => telegram.close(), 900);
    }
  } catch (error) {
    statusElement.textContent = error.message;
    button.disabled = false;
  }
});