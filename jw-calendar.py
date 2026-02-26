import os
import sys
import re
import json

import chompjs as cj
import icalendar as ic
import requests as req
from icalendar.prop.recur.recur import vRecur
from dateutil.rrule import rrule, WEEKLY
from datetime import date, timedelta

JW_BASE  = "https://uspdigital.usp.br/jupiterweb";
JW_AUTH  = JW_BASE+"/autenticar";
JW_SCHED = JW_BASE+"/dwr/call/plaincall/GradeHorariaControleDWR.obterGradeHoraria.dwr";
JW_INFO  = JW_BASE+"/dwr/call/plaincall/DisciplinaControleDWR.obterTurmaEvolucaoCurso.dwr";

jw_auth_data = {
    "url": None,
};

jw_sched_data = {
    "callCount": "1",
    "nextReverseAjaxIndex": "0",
    "c0-scriptName": "GradeHorariaControleDWR",
    "c0-methodName": "obterGradeHoraria",
    "c0-id": "0",
    "c0-param1": "string:1",
    "batchId": "1",
    "instanceId": "0",
    "page": "%2Fjupiterweb%2FgradeHoraria%3F",
};

jw_info_data = {
    "callCount": "1",
    "nextReverseAjaxIndex": "0",
    "c0-scriptName": "DisciplinaControleDWR",
    "c0-methodName": "obterTurmaEvolucaoCurso",
    "c0-id": "0",
    "batchId": "1",
    "instanceId": "0",
    "page": "%2Fjupiterweb%2FgradeHoraria%3F",
};

WDS = {
    "seg": "MO",
    "ter": "TU",
    "qua": "WE",
    "qui": "TH",
    "sex": "FR",
};

def main():
    s = req.session();

    id_usp = os.getenv("ID_USP");
    pass_usp = os.getenv("PASS_USP");
    program_no = os.getenv("PROGRAM_NO");

    if not id_usp or not pass_usp:
        print("ID_USP/PASS_USP env variables missing");
        exit(1);

    jw_auth_data["codpes"] = id_usp;
    jw_auth_data["senusu"] = pass_usp;
    jw_sched_data["c0-param0"] = id_usp;

    auth_res  = s.post(JW_AUTH,  data=jw_auth_data);
    if "Usuário / Senha Incorreta!" in auth_res.text:
        print("auth error");
        exit(1);

    jw_sched_data["scriptSessionId"] = jw_info_data["scriptSessionId"] = s.cookies.get("SSOSESSIONID");
    jw_info_data["scriptSessionId"]  = s.cookies.get("SSOSESSIONID");

    if (program_no):
        jw_sched_data['c0-param1'] = 'string:'+str(program_no);

    sched_res = s.post(JW_SCHED, data=jw_sched_data);
    sched_s = sched_res.text;

    il = list(map(lambda o: o.start(), re.finditer(r"}", sched_s)))
    sched_js = sched_s[sched_s.find("codpes")-1:il[-2]+1];
    sched_raw= list(cj.parse_js_objects(sched_js));

    cal = ic.Calendar();

    for p in sched_raw:
        for idx, (wd, wd_r) in enumerate(WDS.items()):
            # if the course doesn't have a schedule (such as 'TCC/Estagio'), skip it
            if p["horent"]=="null" or p["horsai"]=="null" or p[wd]=="null":
                continue
            start_t = list(map(int, p["horent"].split(":")));
            end_t = list(map(int, p["horsai"].split(":")));
            name = p[wd][1:p[wd].find("-")] if p[wd]!="null" else None;

            if name:
                cod_tur = p[wd].strip()[p[wd].find("-")+1:-2];

                jw_info_data["c0-param0"] = f"string:{name}";
                info_res = s.post(JW_INFO, data=jw_info_data);
                info_s = info_res.text;

                il = list(map(lambda o: o.start(), re.finditer(r"}", info_s)))
                info_js  = info_s[info_s.find("anoIngresso")-1:il[-2]+1];
                info_raw = next(cj.parse_js_objects(info_js));

                tur = next(t for t in info_raw["turmas"] if t["codtur"]==cod_tur);
                name_full =  tur["nomdis"];

                ev = ic.Event();
                ev.add("summary", name_full);
                ev.add(
                    "dtstart",
                    rrule(
                        freq=WEEKLY,
                        dtstart=date.today(),
                        byweekday=idx,
                        count=1
                    )[0].replace(hour=start_t[0],minute=start_t[1])
                );
                ev.add(
                    "dtend",
                    rrule(
                        freq=WEEKLY,
                        dtstart=date.today(),
                        byweekday=idx,
                        count=1
                    )[0].replace(hour=end_t[0],minute=end_t[1])
                );
                ev.add("rrule", vRecur({"FREQ": ["WEEKLY"], "BYDAY": wd_r}));
                ev.add("location", tur["obstur"].replace("\r\n", " "));
                ev.add("status", "CONFIRMED");

                al = ic.Alarm();
                al.add("action", "DISPLAY");
                al.add("description", f"{name_full}");
                al.add("trigger", timedelta(days=-1));
                ev.add_component(al);
                al = ic.Alarm();
                al.add("action", "DISPLAY");
                al.add("description", f"{name_full}");
                al.add("trigger", timedelta(hours=-1));
                ev.add_component(al);

                cal.add_component(ev);

    print(cal.to_ical().decode("utf-8"));

if __name__ == "__main__":
    main();
