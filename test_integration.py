"""
Test integration for the lazy-load architecture.
"""

import asyncio
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, "/home/nekofi/workspace/idea/experiment_skills_mcp")

from framework.skill_manager import SkillManager

async def test():
    print("=" * 50)
    print("    Lazy-Load Integration Test")
    print("=" * 50)

    project_root = Path("/home/nekofi/workspace/idea/experiment_skills_mcp")
    mgr = SkillManager(project_root / "skills")
    
    # 1. Registry
    print("\n[1] Scanning Skills...")
    registry = mgr.scan_and_register()
    assert "mcp-math" in registry
    print(f"    ✅ Found skills: {list(registry.keys())}")
    
    # 2. Catalog Prompt
    catalog = mgr.build_catalog_prompt()
    assert "mcp-math" in catalog
    assert "activate_skill" in catalog
    print(f"    ✅ Catalog prompt built")
    
    # 3. Activation Hook
    print("\n[2] Testing Hook & Activation...")
    mcps_started = []
    
    async def mock_hook(manager, name):
        mcps_started.append(name)
        return "Hook called!"
        
    mgr.register_activation_hook("mcp-math", mock_hook)
    
    res = await mgr.activate_skill("mcp-math")
    assert res["status"] == "activated"
    assert "math__" in res["content"] # text from new SKILL.md
    assert "mcp-math" in mcps_started
    
    print(f"    ✅ Skill loaded content: {len(res['content'])} chars")
    print(f"    ✅ Hook triggered: {res['side_effects']}")
    
    # 4. Deactivation
    print("\n[3] Testing Deactivation...")
    await mgr.deactivate_skill("mcp-math")
    assert not mgr.is_active("mcp-math")
    print("    ✅ Skill deactivated")
    
    print("\n" + "=" * 50)
    print("    ALL LAZY LOAD TESTS PASSED ✅")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test())
