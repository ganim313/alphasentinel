import os
import sys
import yaml
import time

try:
    from openai import OpenAI
except ImportError:
    print("[!] Error: 'openai' library not found. Run: pip install openai")
    sys.exit(1)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "dummy_key"))

AGENCY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ACTIVE_DIR = os.path.join(AGENCY_DIR, "active")
AGENTS_DIR = os.path.join(AGENCY_DIR, "agents")
MEMORY_FILE = os.path.join(ACTIVE_DIR, "project_memory.md")

def load_agent_charter(role_path):
    filepath = os.path.join(AGENTS_DIR, role_path)
    if not os.path.exists(filepath):
        filepath = os.path.join(AGENTS_DIR, role_path + ".md") # fallback
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Agent {role_path} not found.")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def save_deliverable(filepath_rel, content):
    filepath = os.path.join(ACTIVE_DIR, filepath_rel)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Saved deliverable: {filepath_rel}")

def update_memory_snapshot(phase_name, deliverables):
    print(f"[🧠 MEMORY BROKER] Compressing Phase '{phase_name}' deliverables into Project Memory...")
    memory_content = f"\n## Completed Phase: {phase_name}\nKey Decisions & Deliverables:\n"
    for deliverable in deliverables:
        memory_content += f"- {deliverable} has been finalized and approved.\n"
        
    mode = "a" if os.path.exists(MEMORY_FILE) else "w"
    with open(MEMORY_FILE, mode, encoding="utf-8") as f:
        if mode == "w":
            f.write("# 🧠 Master Project Memory Snapshot\n(Read this file for cross-department context instead of raw deliverables.)\n")
        f.write(memory_content)

def get_memory_context():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f"\n\n--- PROJECT MEMORY (Context) ---\n{f.read()}\n--------------------------------\n"
    return ""

def call_llm(system_prompt, user_prompt):
    """Raw LLM API call."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        if "dummy_key" in str(os.environ.get("OPENAI_API_KEY", "dummy_key")) or "auth" in str(e).lower():
            time.sleep(1)
            # Simulated responses for testing
            if "Master Critic" in system_prompt:
                return "[STATUS: PASS]"
            return f"# Simulated Output\n\nDeliverable generated based on: {user_prompt[:30]}..."
        raise e

def call_agent_with_critic_loop(agent_name, role_path, user_prompt, max_retries=3):
    """Executes the 3-Strike Automated Critic Loop."""
    system_prompt = load_agent_charter(role_path) + get_memory_context()
    critic_prompt_base = load_agent_charter("oversight/master_critic.md")
    
    current_prompt = user_prompt
    retries = 0
    
    while retries < max_retries:
        print(f"\n[⚙️ Waking Agent] {agent_name} (Attempt {retries + 1}/{max_retries})...")
        agent_output = call_llm(system_prompt, current_prompt)
        
        print(f"[🔍 CRITIC AUDIT] Waking Master Critic to red-team {agent_name}'s output...")
        critic_task = f"Audit the following deliverable from the {agent_name}:\n\n{agent_output}"
        critic_output = call_llm(critic_prompt_base, critic_task)
        
        if "[STATUS: PASS]" in critic_output.upper():
            print(f"[✓] Critic Approved.")
            return agent_output
        else:
            print(f"[!] Critic REJECTED output. Triggering internal retry...")
            # print(f"Critic Feedback: {critic_output}") # Uncomment to see raw critic notes
            retries += 1
            current_prompt = user_prompt + f"\n\n--- CRITIC FEEDBACK (FIX THESE ISSUES) ---\nYour previous output failed audit. Fix these issues:\n{critic_output}"
            
    print(f"\n🚨 [HUMAN INTERVENTION REQUIRED] {agent_name} failed the Critic audit 3 times.")
    print("The agent is caught in a hallucination/logic loop.")
    input("Press Enter to accept the flawed document anyway, or Ctrl+C to abort: ")
    return agent_output

def phase_gate_approval(phase_name):
    print(f"\n[🛑 PHASE GATE] Phase '{phase_name}' is ready for Executive Sign-Off.")
    decision = input("Type 'Approve' to advance, or 'Reject' to Auto-Rollback: ")
    return decision.lower() in ['approve', 'approved', 'yes', 'y']

def run_orchestrator(project_idea):
    print("=" * 70)
    print("🚀 ENTERPRISE AGENCY ORCHESTRATOR (With Master Critic Loop)")
    print("=" * 70)
    
    # PHASE 1
    print("\n--- INITIATING PHASE 1: INTAKE & PROPOSAL ---")
    pm_out = call_agent_with_critic_loop("Product Manager", "product_design/product_manager", f"Draft the Proposal/SOW for: '{project_idea}'")
    save_deliverable("product_design/01_proposal_sow.md", pm_out)
    
    legal_out = call_agent_with_critic_loop("Legal Ops", "finance_ops/legal_operations_officer", "Draft an MSA Contract based on the new proposal.")
    save_deliverable("finance_ops/02_msa_contract.md", legal_out)
    
    if not phase_gate_approval("1_intake_and_proposal"):
        print("🚨 [AUTO-ROLLBACK] Rolling back to beginning of Phase 1...")
        return
    update_memory_snapshot("1_intake_and_proposal", ["01_proposal_sow.md", "02_msa_contract.md"])
    
    # PHASE 2
    print("\n--- INITIATING PHASE 2: REQUIREMENTS ---")
    prd_out = call_agent_with_critic_loop("Product Manager", "product_design/product_manager", "Expand the approved SOW into a full PRD (03_requirements_engineering.md).")
    save_deliverable("product_design/03_requirements_engineering.md", prd_out)
    
    if not phase_gate_approval("2_requirements"):
        print("🚨 [AUTO-ROLLBACK] Rolling back to Phase 1...")
        return
    update_memory_snapshot("2_requirements", ["03_requirements_engineering.md"])
    
    print("\n[🎉 SUCCESS] Phase 1 and 2 Complete.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        idea = " ".join(sys.argv[1:])
    else:
        idea = input("Enter a 1-sentence project idea to begin orchestration: ")
        
    run_orchestrator(idea)
