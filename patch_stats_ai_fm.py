import re

with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()

target = """    def _map_ai_fm_text_to_icon(self, text):
        t = text.lower()
        if "terrain" in t or "grouser" in t: return "additionalGrousers"
        if "lightweight" in t or "friction" in t: return "betterFriction"
        if "parallax" in t or "aiming" in t: return "improvedAimingHandling"
        if "powder" in t or "scope" in t: return "improvedScope"
        if "right-angle" in t or "observation" in t: return "improvedObservationDevice"
        if "anti-reflective" in t or "spalling" in t or "lenses" in t or "headlight" in t: return "improvedSpallingResistance"
        if "power supply" in t or "tuning" in t or "wheels" in t: return "improvedTurretTurningWheels"
        if "shielding" in t or "filter" in t or "isolation" in t: return "improvedLightFilters"
        if "durability" in t or "suspension" in t: return "improvedTurretTurningWheels"
        if "valve" in t or "gears" in t: return "improvedAimingHandling"
        return "glow" """

new_logic = """    def _map_ai_fm_text_to_icon(self, text):
        t = text.lower()
        # Robust keyword mapping for all 25 field mod IDs
        if "durability" in t or "chassis durability" in t: return "improvedChassisDurability"
        if "stability" in t and "chassis" in t: return "improvedChassisStability"
        if "aiming" in t or "parallax" in t or "gears" in t or "valve" in t: return "improvedAimingHandling"
        if "camouflage" in t or "concealment" in t: return "improvedCamouflage"
        if "engine" in t or "power" in t: return "improvedEnginePower"
        if "breech" in t: return "improvedGunBreech"
        if "filter" in t or "shielding" in t or "isolation" in t: return "improvedLightFilters"
        if "muzzle" in t: return "improvedMuzzleBreak"
        if "observation" in t or "right-angle" in t: return "improvedObservationDevice"
        if "reflex" in t: return "improvedReflexScopes"
        if "scope" in t or "powder" in t: return "improvedScope"
        if "tracks" in t or "self-repairing tracks" in t: return "improvedSelfRepairingTracks"
        if "wheels" in t and "repairing" in t: return "improvedSelfRepairingWheels"
        if "sharpness" in t or "visor" in t: return "improvedSharpnessVisor"
        if "spalling" in t or "lenses" in t or "reflective" in t or "headlight" in t: return "improvedSpallingResistance"
        if "backwards" in t or "reverse" in t: return "improvedSpeedIndicatorBackwards"
        if "speed" in t or "forward" in t: return "improvedSpeedIndicator"
        if "ring" in t: return "improvedTurretRingStability"
        if "tuning" in t or "turret turning" in t or "suspension" in t: return "improvedTurretTurningWheels"
        if "sensitivity" in t or "optics" in t: return "increasedSensitivityOptics"
        if "thickness" in t or "armor" in t: return "increasedThickness"
        if "interior" in t or "modules" in t: return "reinforcedInteriorModules"
        if "structure" in t: return "reinforcedStructure"
        if "terrain" in t or "grouser" in t: return "additionalGrousers"
        if "lightweight" in t or "friction" in t: return "betterFriction"
        return "glow" """

if target in src:
    src = src.replace(target, new_logic)
    with open('stats_ai.py', 'w', encoding='utf-8') as f:
        f.write(src)
    print("Patched stats_ai.py _map_ai_fm_text_to_icon")
else:
    print("Target block not found in stats_ai.py!")
