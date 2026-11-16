// Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// AI-generated project code: written and modified with OpenAI Codex.
// Interactive presentation fixtures. All changes remain in this process.
using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;

namespace NativeWpf
{
    public sealed class NativeLayoutDemo
    {
        readonly JavaScriptSerializer _json=new JavaScriptSerializer();
        readonly Action<string> _receive;
        readonly Dictionary<string,object> _snapshot;

        public NativeLayoutDemo(string path,Action<string> receive)
        {
            _receive=receive;
            _snapshot=_json.Deserialize<Dictionary<string,object>>(File.ReadAllText(path));
        }

        public void Publish()
        {
            _receive(_json.Serialize(new { type="snapshot",snapshot=_snapshot }));
        }

        public void Handle(Dictionary<string,object> message)
        {
            string type=(string)message["type"];
            if (type=="set")
            {
                Dictionary<string,object> settings=(Dictionary<string,object>)_snapshot["settings"];
                settings[(string)message["name"]]=message["value"];
                Publish();
                return;
            }
            if (type!="action") return;
            string name=(string)message["name"];
            Dictionary<string,object> args=(Dictionary<string,object>)message["args"];
            object data=null;
            if (name=="documents") data=_snapshot["documents"];
            if (name=="cleanup_batches")
            {
                HashSet<string> selected=new HashSet<string>();
                foreach (object value in (System.Collections.IEnumerable)args["names"]) selected.Add((string)value);
                List<object> retained=new List<object>();
                foreach (Dictionary<string,object> item in (System.Collections.IEnumerable)_snapshot["batches"])
                    if (!selected.Contains((string)item["name"]) || (bool)item["protected"]) retained.Add(item);
                _snapshot["batches"]=retained;
                Dictionary<string,object> space=(Dictionary<string,object>)_snapshot["space"];
                long total=0,cleanable=0;
                foreach (Dictionary<string,object> item in retained)
                {
                    long bytes=Convert.ToInt64(item["bytes"]);
                    total+=bytes;
                    if (!(bool)item["protected"]) cleanable+=bytes;
                }
                space["used_bytes"]=total+184L*1024*1024;space["cleanable_bytes"]=cleanable;space["protected_bytes"]=total-cleanable+184L*1024*1024;
                space["segments"]=new[] {
                    new { label="截图批次",bytes=total*4/5,color="#1D7961" },
                    new { label="诊断摘要",bytes=total-total*4/5,color="#4E7F99" },
                    new { label="格式化 JSON",bytes=30L*1024*1024,color="#C19343" },
                    new { label="工作簿",bytes=4L*1024*1024,color="#8E9B92" },
                    new { label="学习成果",bytes=150L*1024*1024,color="#7C719B" }};
            }
            if (name=="update_shortcuts")
            {
                Dictionary<string,object> runtime=(Dictionary<string,object>)_snapshot["runtime"];
                Dictionary<string,object> shortcuts=(Dictionary<string,object>)runtime["shortcuts"];
                Dictionary<string,object> values=(Dictionary<string,object>)args["values"];
                string[] fields={"hotkey","single_hotkey","montage_hotkey","cancel_hotkey","quit_hotkey","overlay_hotkey"};
                string[] labels={"full","single","puzzle","abort","stop","overlay"};
                foreach (KeyValuePair<string,object> pair in values) shortcuts[labels[Array.IndexOf(fields,pair.Key)]]=pair.Value;
            }
            _receive(_json.Serialize(new { type="action_result",request_id=message["request_id"],ok=true,data=data }));
            Publish();
            if (name!="documents" && name!="save_preferences" && name!="update_shortcuts")
                _receive(_json.Serialize(new { type="toast",text="演示操作已完成，修改仅在本次预览中保留。" }));
        }
    }
}
