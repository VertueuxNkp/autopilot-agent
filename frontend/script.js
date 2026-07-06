// ─── CONFIGURATION ─────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000/api";
const WS_BASE = "ws://localhost:8000";

// ─── ÉTAT DE L'APPLICATION ─────────────────────────────────────────────────────
let currentWorkflowId = null;
let websocket = null;

// ─── UTILITAIRES ───────────────────────────────────────────────────────────────

function setExample(text) {
    document.getElementById("requestInput").value = text;
}

function showCard(cardId) {
    const cards = ["clarificationCard", "checkpointCard", "resultCard"];
    cards.forEach(id => {
        const card = document.getElementById(id);
        if (id === cardId) {
            card.classList.remove("hidden");
        } else {
            card.classList.add("hidden");
        }
    });
}

function hideAllCards() {
    ["clarificationCard", "checkpointCard", "resultCard"].forEach(id => {
        document.getElementById(id).classList.add("hidden");
    });
}

function setStatus(message, type = "") {
    const el = document.getElementById("reasoningStatus");
    el.textContent = message;
    el.className = `reasoning-status ${type}`;
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

function addLog(log) {
    const container = document.getElementById("reasoningLogs");

    // Supprimer l'empty state si présent
    const emptyState = container.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    const icons = {
        info: "→",
        warning: "⚠️",
        error: "✗"
    };

    const icon = icons[log.type] || "→";
    const time = formatTime(log.timestamp || Date.now());

    const logEl = document.createElement("div");
    logEl.className = `log-item ${log.type || "info"}`;
    logEl.innerHTML = `
        <span class="log-icon">${icon}</span>
        <div class="log-content">
            <div class="log-step">Étape ${log.step || "?"}</div>
            <div class="log-message">${log.message}</div>
        </div>
        <span class="log-time">${time}</span>
    `;

    container.appendChild(logEl);
    container.scrollTop = container.scrollHeight;
}

function clearLogs() {
    const container = document.getElementById("reasoningLogs");
    container.innerHTML = `
        <div class="empty-state">
            <span>🤖</span>
            <p>Les étapes de raisonnement de l'agent apparaîtront ici en temps réel</p>
        </div>
    `;
}

function setConnectionStatus(connected) {
    const badge = document.getElementById("connectionStatus");
    const span = badge.querySelector("span:last-child");
    if (connected) {
        badge.classList.add("connected");
        span.textContent = "WebSocket connecté";
    } else {
        badge.classList.remove("connected");
        span.textContent = "Déconnecté";
    }
}

// ─── WEBSOCKET ──────────────────────────────────────────────────────────────────

function connectWebSocket(workflowId) {
    // Fermer la connexion précédente si elle existe
    if (websocket) {
        websocket.close();
    }

    websocket = new WebSocket(`${WS_BASE}/ws/${workflowId}`);

    websocket.onopen = () => {
        setConnectionStatus(true);
        console.log(`[WS] Connecté pour workflow ${workflowId}`);

        // Ping toutes les 30 secondes pour garder la connexion active
        setInterval(() => {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("[WS] Message reçu:", data);

        if (data.type === "reasoning_log") {
            addLog(data);
        } else if (data.type === "status_update") {
            handleStatusUpdate(data);
        } else if (data.type === "pong") {
            console.log("[WS] Pong reçu");
        }
    };

    websocket.onclose = () => {
        setConnectionStatus(false);
        console.log("[WS] Connexion fermée");
    };

    websocket.onerror = (error) => {
        console.error("[WS] Erreur:", error);
        setConnectionStatus(false);
    };
}

function handleStatusUpdate(data) {
    const { status, data: statusData } = data;

    if (status === "checkpoint_required") {
        showCheckpoint(statusData.checkpoint_data);
    } else if (status === "clarification_required") {
        showClarification(statusData.clarification_question);
    } else if (status === "executed") {
        showResult(true, "Action confirmée et exécutée avec succès !");
    } else if (status === "failed") {
        showResult(false, "Workflow annulé ou échoué.");
    }
}

// ─── ACTIONS PRINCIPALES ────────────────────────────────────────────────────────

async function submitWorkflow() {
    const userId = document.getElementById("userId").value.trim();
    const request = document.getElementById("requestInput").value.trim();

    if (!userId || !request) {
        alert("Veuillez remplir l'identifiant utilisateur et la demande.");
        return;
    }

    // Reset UI
    clearLogs();
    hideAllCards();
    currentWorkflowId = null;

    // Désactiver le bouton
    const btn = document.getElementById("submitBtn");
    btn.disabled = true;
    btn.textContent = "⏳ Traitement en cours...";

    setStatus("Connexion à l'agent...", "running");

    try {
        // Appel API
        const response = await fetch(`${API_BASE}/workflow`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, request })
        });

        const result = await response.json();
        currentWorkflowId = result.workflow_id;

        // Afficher le workflow ID
        document.getElementById("workflowIdDisplay").textContent =
            `ID: ${currentWorkflowId.substring(0, 8)}...`;

        // Connecter le WebSocket
        connectWebSocket(currentWorkflowId);

        // Charger les logs existants depuis l'API
        await loadLogs(currentWorkflowId);

        // Gérer le statut
        handleApiStatus(result);

    } catch (error) {
        console.error("Erreur:", error);
        setStatus("Erreur de connexion au serveur", "error");
        addLog({
            step: 0,
            message: `Erreur : ${error.message}`,
            timestamp: Date.now(),
            type: "error"
        });
    } finally {
        btn.disabled = false;
        btn.textContent = "🚀 Lancer le workflow";
    }
}

async function loadLogs(workflowId) {
    try {
        const response = await fetch(`${API_BASE}/workflow/${workflowId}/logs`);
        const data = await response.json();

        if (data.logs && data.logs.length > 0) {
            clearLogs();
            data.logs.forEach(log => addLog(log));
        }
    } catch (error) {
        console.error("Erreur chargement logs:", error);
    }
}

function handleApiStatus(result) {
    const { status, clarification_question, checkpoint_data, next_step } = result;

    if (status === "clarification_required") {
        setStatus("⚠️ Clarification requise", "running");
        showClarification(clarification_question || next_step);

    } else if (status === "checkpoint_required") {
        setStatus("⚠️ Confirmation requise", "running");
        showCheckpoint(checkpoint_data);

    } else if (status === "executed") {
        setStatus("✅ Workflow terminé", "done");
        showResult(true, next_step || "Workflow exécuté avec succès !");

    } else if (status === "failed") {
        setStatus("❌ Workflow échoué", "error");
        showResult(false, next_step || "Le workflow a échoué.");

    } else {
        setStatus("✅ Workflow traité", "done");
        showResult(true, next_step || "Workflow traité.");
    }
}

function showClarification(question) {
    document.getElementById("clarificationQuestion").textContent = question;
    document.getElementById("clarificationAnswer").value = "";
    showCard("clarificationCard");
    document.getElementById("clarificationAnswer").focus();
}

function showCheckpoint(checkpointData) {
    const details = document.getElementById("checkpointDetails");

    if (checkpointData && typeof checkpointData === "object") {
        const action = checkpointData.action || "action";
        const args = checkpointData.args || {};
        const result = checkpointData.result || {};

        let html = `<strong>Action :</strong> ${action}<br><br>`;

        if (action === "send_email") {
            html += `<strong>Destinataire :</strong> ${args.recipient || "?"}<br>`;
            html += `<strong>Sujet :</strong> ${args.subject || "?"}<br>`;
            html += `<strong>Corps :</strong><br>${(args.body || "").substring(0, 200)}...`;
        } else if (action === "generate_quote") {
            html += `<strong>Client :</strong> ${args.customer_name || "?"}<br>`;
            html += `<strong>Articles :</strong> ${(args.items || []).join(", ")}<br>`;
            html += `<strong>Total TTC :</strong> ${result.total_ttc || "?"}€`;
        } else if (action === "schedule_meeting") {
            html += `<strong>Participant :</strong> ${args.attendee || "?"}<br>`;
            html += `<strong>Date :</strong> ${args.date || "?"} à ${args.time || "?"}<br>`;
            html += `<strong>Durée :</strong> ${args.duration || "?"}min`;
        } else {
            html += JSON.stringify(checkpointData, null, 2);
        }

        details.innerHTML = html;
    } else {
        details.textContent = "Confirmer l'action ?";
    }

    showCard("checkpointCard");
}

function showResult(success, message) {
    const card = document.getElementById("resultCard");
    const title = document.getElementById("resultTitle");
    const msg = document.getElementById("resultMessage");

    card.className = `card ${success ? "success" : "failed"}`;
    title.textContent = success ? "✅ Workflow terminé" : "❌ Workflow échoué";
    msg.textContent = message;

    showCard("resultCard");
    setStatus(success ? "✅ Terminé avec succès" : "❌ Échoué", success ? "done" : "error");
}

// ─── RÉPONDRE À UNE CLARIFICATION ──────────────────────────────────────────────

async function sendReply() {
    const answer = document.getElementById("clarificationAnswer").value.trim();
    if (!answer) {
        alert("Veuillez entrer une réponse.");
        return;
    }

    if (!currentWorkflowId) return;

    hideAllCards();
    setStatus("⏳ Traitement de votre réponse...", "running");

    try {
        const response = await fetch(`${API_BASE}/workflow/${currentWorkflowId}/reply`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ answer })
        });

        const result = await response.json();

        // Charger les nouveaux logs
        await loadLogs(currentWorkflowId);

        // Gérer le nouveau statut
        handleApiStatus(result);

    } catch (error) {
        console.error("Erreur:", error);
        setStatus("Erreur lors de la réponse", "error");
    }
}

// ─── CONFIRMER OU ANNULER UN CHECKPOINT ────────────────────────────────────────

async function confirmAction(confirmed) {
    if (!currentWorkflowId) return;

    hideAllCards();
    setStatus(confirmed ? "⏳ Exécution en cours..." : "⏳ Annulation...", "running");

    try {
        const response = await fetch(`${API_BASE}/workflow/${currentWorkflowId}/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirmed })
        });

        const result = await response.json();
        handleApiStatus(result);

        // Ajouter un log final
        addLog({
            step: 99,
            message: confirmed
                ? "✅ Action confirmée et exécutée"
                : "❌ Action annulée par l'utilisateur",
            timestamp: Date.now(),
            type: confirmed ? "info" : "warning"
        });

    } catch (error) {
        console.error("Erreur:", error);
        setStatus("Erreur lors de la confirmation", "error");
    }
}

// ─── RESET ──────────────────────────────────────────────────────────────────────

function resetWorkflow() {
    currentWorkflowId = null;

    if (websocket) {
        websocket.close();
        websocket = null;
    }

    clearLogs();
    hideAllCards();
    setStatus("En attente d'une demande...", "");
    setConnectionStatus(false);

    document.getElementById("workflowIdDisplay").textContent = "";
    document.getElementById("requestInput").value = "";
    document.getElementById("submitBtn").disabled = false;
}

// ─── INITIALISATION ─────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    // Permettre d'envoyer avec Ctrl+Enter dans le textarea
    document.getElementById("requestInput").addEventListener("keydown", (e) => {
        if (e.ctrlKey && e.key === "Enter") {
            submitWorkflow();
        }
    });

    // Permettre d'envoyer avec Enter dans le champ de clarification
    document.getElementById("clarificationAnswer").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            sendReply();
        }
    });

    console.log("🤖 Autopilot Agent Frontend chargé !");
});