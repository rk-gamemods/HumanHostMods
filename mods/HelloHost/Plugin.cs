using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace HelloHost
{
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    public class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "rkgamemods.humanhost.hellohost";
        public const string PluginName = "Hello Host";
        public const string PluginVersion = "0.1.0";

        internal static ManualLogSource Log;

        private ConfigEntry<bool> _logOnStart;
        private Harmony _harmony;

        private void Awake()
        {
            Log = Logger;
            _logOnStart = Config.Bind("General", "LogOnStart", true,
                "Write the game and Unity version to the BepInEx log on startup.");

            _harmony = new Harmony(PluginGuid);
            _harmony.PatchAll(typeof(Plugin).Assembly);

            if (_logOnStart.Value)
            {
                Log.LogInfo($"{PluginName} {PluginVersion} loaded | game {Application.version} | Unity {Application.unityVersion}");
            }
        }

        private void OnDestroy()
        {
            _harmony?.UnpatchSelf();
        }
    }
}
