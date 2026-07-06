import requests
import json
import time

BASE_URL = "http://localhost:8000/api"


def print_result(title: str, response: dict, expected_status: str = None):
    print(f"\n{'='*50}")
    print(f"TEST : {title}")
    print(f"{'='*50}")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    if expected_status:
        status = response.get("status")
        if status == expected_status:
            print(f"✅ Status correct : {status}")
        else:
            print(f"❌ Status incorrect : attendu '{expected_status}', reçu '{status}'")


def test_simple_email():
    """Scénario 1 — Email avec adresse valide"""
    print("\n🧪 SCÉNARIO 1 — Email avec adresse valide")

    response = requests.post(f"{BASE_URL}/workflow", json={
        "user_id": "test-user-001",
        "request": "Envoie un email à jean@example.com pour confirmer la réunion de demain"
    })
    result = response.json()
    print_result("Créer workflow email valide", result, "checkpoint_required")
    return result.get("workflow_id")


def test_clarification():
    """Scénario 2 — Demande avec info manquante"""
    print("\n🧪 SCÉNARIO 2 — Demande avec clarification")

    response = requests.post(f"{BASE_URL}/workflow", json={
        "user_id": "test-user-002",
        "request": "Envoie un devis à Jean"
    })
    result = response.json()
    print_result("Créer workflow avec info manquante", result, "clarification_required")

    workflow_id = result.get("workflow_id")
    if workflow_id and result.get("status") == "clarification_required":
        # Répondre à la clarification
        time.sleep(1)
        reply = requests.post(f"{BASE_URL}/workflow/{workflow_id}/reply", json={
            "answer": "Le prix est 500 euros pour le produit ABC"
        })
        print_result("Répondre à la clarification", reply.json())

    return workflow_id


def test_fallback():
    """Scénario 3 — Email avec adresse invalide → fallback"""
    print("\n🧪 SCÉNARIO 3 — Fallback avec email invalide")

    response = requests.post(f"{BASE_URL}/workflow", json={
        "user_id": "test-user-003",
        "request": "Envoie un email à jean@invalide pour confirmer la commande"
    })
    result = response.json()
    print_result("Créer workflow email invalide", result, "clarification_required")
    return result.get("workflow_id")


def test_confirm():
    """Scénario 4 — Confirmation d'un checkpoint"""
    print("\n🧪 SCÉNARIO 4 — Confirmation checkpoint")

    response = requests.post(f"{BASE_URL}/workflow", json={
        "user_id": "test-user-004",
        "request": "Envoie un email à marie@company.com pour lui envoyer le rapport mensuel"
    })
    result = response.json()
    workflow_id = result.get("workflow_id")

    if workflow_id and result.get("status") == "checkpoint_required":
        time.sleep(1)
        confirm = requests.post(f"{BASE_URL}/workflow/{workflow_id}/confirm", json={
            "confirmed": True
        })
        print_result("Confirmer le checkpoint", confirm.json(), "executed")
    else:
        print_result("Créer workflow pour confirmation", result)

    return workflow_id


def test_cancel():
    """Scénario 5 — Annulation d'un checkpoint"""
    print("\n🧪 SCÉNARIO 5 — Annulation checkpoint")

    response = requests.post(f"{BASE_URL}/workflow", json={
        "user_id": "test-user-005",
        "request": "Envoie un email à paul@business.com pour annuler la réunion"
    })
    result = response.json()
    workflow_id = result.get("workflow_id")

    if workflow_id and result.get("status") == "checkpoint_required":
        time.sleep(1)
        cancel = requests.post(f"{BASE_URL}/workflow/{workflow_id}/confirm", json={
            "confirmed": False
        })
        print_result("Annuler le checkpoint", cancel.json(), "failed")
    else:
        print_result("Créer workflow pour annulation", result)

    return workflow_id


def test_get_logs(workflow_id: str):
    """Vérifier les logs d'un workflow"""
    if not workflow_id:
        return

    response = requests.get(f"{BASE_URL}/workflow/{workflow_id}/logs")
    result = response.json()
    print(f"\n📋 LOGS du workflow {workflow_id[:8]}...")
    for log in result.get("logs", []):
        icon = "✅" if log["type"] == "info" else "⚠️" if log["type"] == "warning" else "❌"
        print(f"  {icon} Step {log['step']} : {log['message']}")


def test_supabase_persistence(workflow_id: str):
    """Vérifier que le workflow est bien dans Supabase"""
    if not workflow_id:
        return

    response = requests.get(f"{BASE_URL}/workflow/{workflow_id}")
    result = response.json()
    print(f"\n💾 SUPABASE — Workflow {workflow_id[:8]}...")
    print(f"  Status : {result.get('status')}")
    print(f"  Logs count : {len(result.get('logs', []))}")
    if result.get("status"):
        print("  ✅ Workflow persisté dans Supabase")


if __name__ == "__main__":
    print("🚀 DÉMARRAGE DES TESTS AUTOPILOT AGENT")
    print("="*50)

    # Scénario 1
    wf1 = test_simple_email()
    test_get_logs(wf1)
    test_supabase_persistence(wf1)

    time.sleep(2)

    # Scénario 2
    wf2 = test_clarification()
    test_get_logs(wf2)

    time.sleep(2)

    # Scénario 3
    wf3 = test_fallback()
    test_get_logs(wf3)

    time.sleep(2)

    # Scénario 4
    wf4 = test_confirm()
    test_get_logs(wf4)

    time.sleep(2)

    # Scénario 5
    wf5 = test_cancel()
    test_get_logs(wf5)

    print("\n\n🏁 TESTS TERMINÉS")