"""Builds src/overheard/data/seed_today.json: the 60 hand-written voicemails of "today" (Tue 2026-03-10) at the
Federal Benefits Service Center, with ground truth and the case-system facts each caller's case needs, plus 120
junk calls (robocalls, scams, silence, hang-ups, wrong numbers, pocket dials) generated from templates with a fixed
seed, so the day has twice as much junk as real calls. The scripts are the hand-written part; this file assembles
them, generates the junk and checks the planted signals. Run it after editing."""
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "overheard" / "data" / "seed_today.json"
M, CASES = [], {}


def case(cid, name, phone, *, status, payments=(), docs=(), last, team, region, lang="en"):
    CASES[cid] = {"id": cid, "name": name, "phone": phone, "status": status, "region": region, "lang": lang,
                  "payments": [dict(zip(("date", "amount", "status"), p, strict=True)) for p in payments],
                  "docs": [dict(zip(("name", "received"), d, strict=True)) for d in docs], "lastAction": last, "team": team}


def vm(at, phone, dur, script, *, intent, urgency, root, team, name=None, callback=None, case_id=None,
       lang="en", gist=None, group=None, obligations=(), resolvable=None, linked=(), said_case=True,
       window=None, belief=None, junk=None):
    M.append({"receivedAt": at, "callerId": phone, "durationSec": dur, "lang": lang, "script": script.strip(),
              "truth": {"intent": intent, "urgency": urgency, "rootCause": root, "team": team, "callerName": name,
                        "callbackNumber": callback or phone, "caseId": case_id, "caseNumberSaid": said_case,
                        "group": group, "obligations": list(obligations), "resolvableBy": resolvable,
                        "linkedTo": list(linked), "callbackWindow": window, "beliefMismatch": belief,
                        "englishGist": gist, "junk": junk}})


# ---------------------------------------------------------------- the case system (only what today's callers need)
case("FBS-104227", "Dolores Whitfield", "+1-614-555-0142", status="payment held: address re-verification (Form 22-B) pending",
     payments=[("2026-02-03", 1184.00, "paid"), ("2026-03-03", 1184.00, "held")],
     docs=[("Form 22-B", None)], last="2026-02-20 payment held pending re-verification", team="accounts", region="OH")
case("FBS-311902", "Marcus Bell", "+1-404-555-0117", status="active",
     payments=[("2026-02-12", 962.50, "paid"), ("2026-03-12", 962.50, "scheduled")],
     last="2026-02-27 payment date moved to the 12th (calendar change)", team="payments", region="GA")
case("FBS-228810", "Ana Lucía Ortega", "+1-305-555-0163", status="active", lang="es",
     payments=[("2026-03-05", 1040.00, "paid")], docs=[("Bank letter", "2026-03-02")],
     last="2026-03-05 payment issued", team="payments", region="FL")
case("FBS-190455", "Gerald Pruitt", "+1-216-555-0188", status="active",
     docs=[("Birth certificate copy", "2026-03-06"), ("Form 14 (direct deposit)", "2026-03-06")],
     last="2026-03-06 documents scanned", team="documents", region="OH")
case("FBS-402771", "Harold Jennings", "+1-502-555-0109", status="payment returned by bank",
     payments=[("2026-03-03", 1312.00, "returned: account closed")],
     last="2026-03-05 deposit returned; new account details needed", team="payments", region="KY")
case("FBS-377014", "Linh Tran", "+1-714-555-0131", status="active", lang="vi",
     payments=[("2026-03-03", 890.00, "paid")], last="2026-03-03 payment issued", team="payments", region="CA")
case("FBS-266533", "Rosario Dimaculangan", "+1-206-555-0177", status="re-verification requested", lang="tl",
     docs=[("Form 22-B", "2026-02-25")], last="2026-02-25 Form 22-B received", team="accounts", region="WA")
case("FBS-150398", "Teresa Wojcik", "+1-312-555-0155", status="active",
     docs=[("Form 9 (address change)", "2026-03-04")], last="2026-03-06 address updated", team="accounts", region="IL")
case("FBS-319266", "Darnell Hughes", "+1-919-555-0124", status="active",
     payments=[("2026-03-03", 1105.00, "paid")], last="2026-03-03 payment issued", team="payments", region="NC")
case("FBS-284019", "Yolanda Price", "+1-713-555-0146", status="under review",
     docs=[("Medical statement", None)], last="2026-02-18 medical statement requested", team="documents", region="TX")
case("FBS-133702", "Frank Delgado", "+1-702-555-0193", status="active",
     payments=[("2026-03-12", 977.00, "scheduled")], last="2026-02-27 payment date moved to the 12th", team="payments", region="NV")
case("FBS-412688", "Bernice Coleman", "+1-410-555-0115", status="active",
     docs=[("Form 14 (direct deposit)", "2026-03-09")], last="2026-03-09 direct deposit change received", team="accounts", region="MD")
case("FBS-205119", "Samuel Okafor", "+1-614-555-0168", status="appeal pending",
     last="2026-01-14 appeal filed; no decision", team="correspondence", region="OH")
case("FBS-298344", "Patricia Lund", "+1-612-555-0139", status="payment held: identity check",
     payments=[("2026-03-03", 1250.00, "held")], last="2026-02-24 identity check opened", team="correspondence", region="MN")
case("FBS-187520", "Walter Kim", "+1-503-555-0184", status="active",
     payments=[("2026-03-03", 1480.00, "paid")], last="2026-03-03 payment issued", team="accounts", region="OR")
case("FBS-366047", "Ruth Abernathy", "+1-865-555-0102", status="active",
     payments=[("2026-03-03", 845.00, "paid")], last="2026-03-03 payment issued", team="payments", region="TN")
case("FBS-251873", "Kevin Moore", "+1-317-555-0172", status="active",
     docs=[("Form 22-B", "2026-03-02")], last="2026-03-02 Form 22-B received; re-verification complete", team="accounts", region="IN")
case("FBS-170266", "Carmen Reyes", "+1-210-555-0158", status="active", lang="es",
     docs=[("Form 9 (address change)", "2026-03-08")], last="2026-03-08 address change received", team="accounts", region="TX")
case("FBS-345901", "Jim Haskell", "+1-207-555-0133", status="active",
     payments=[("2026-03-03", 1020.00, "paid")], last="2026-03-03 payment issued", team="payments", region="ME")
case("FBS-224417", "Angela Ruiz", "+1-505-555-0187", status="active",
     payments=[("2026-03-12", 1199.00, "scheduled")], last="2026-02-27 payment date moved to the 12th", team="payments", region="NM")

PORTAL = dict(intent="portal_access", root="portal-sign-in-failure", team="portal_support", group="portal-sign-in")

# ---------------------------------------------------------------- yesterday, after hours (in the queue at 8:00)
vm("2026-03-09T16:41", "+1-614-555-0142", 48, """
Hi, this is Dolores Whitfield, case number F B S one oh four two two seven. I'm calling because my March payment
didn't come. I got a letter about a form, the twenty-two B, and I sent that back, I think in February. Could someone
call me back at this number? Thank you.
""", intent="status_payment", urgency=3, root="form-22b-confusion", team="accounts", name="Dolores Whitfield",
   case_id="FBS-104227", resolvable=None, linked=["m03", "m31"])
vm("2026-03-09T17:12", "+1-404-555-0117", 37, """
Yeah, hi, Marcus Bell. Case three one one nine oh two. My payment usually hits on the third and it's the tenth now,
well, the ninth, and nothing. Did something happen? Just want to know if I need to do anything.
""", intent="status_payment", urgency=2, root="payment-date-shift", team="payments", name="Marcus Bell",
   case_id="FBS-311902", resolvable="status_lookup", belief="thinks the payment was missed; it's scheduled for 2026-03-12")
vm("2026-03-09T19:05", "+1-614-555-0142", 71, """
It's Dolores Whitfield again, I called this afternoon. I haven't heard anything. I really need to know what's going on
with my money because rent is due and I already sent that form back. One oh four two two seven. I'm home all
evening. Please call me.
""", intent="status_payment", urgency=3, root="form-22b-confusion", team="accounts", name="Dolores Whitfield",
   case_id="FBS-104227", linked=["m01", "m31"])
vm("2026-03-09T20:33", "+1-305-555-0163", 52, """
Hola, buenas noches, habla Ana Lucía Ortega. Mi número de caso es el dos dos ocho ocho uno cero. Quería saber si
recibieron la carta del banco que mandé la semana pasada, y si mi pago de marzo ya salió. Muchas gracias, que tenga
buena noche.
""", intent="status_document", urgency=2, root="document-received-confirmation", team="payments", lang="es",
   name="Ana Lucía Ortega", case_id="FBS-228810", resolvable="status_lookup",
   gist="Asks whether the bank letter she sent last week arrived and whether her March payment went out.")
vm("2026-03-09T21:58", "+1-216-555-0188", 39, """
Gerald Pruitt here. I mailed in my birth certificate and the direct deposit form, uh, last Monday. Just making sure
you got them. I don't have my case number in front of me, sorry. Thanks.
""", intent="status_document", urgency=2, root="document-received-confirmation", team="documents",
   name="Gerald Pruitt", case_id="FBS-190455", said_case=False, resolvable="status_lookup")
vm("2026-03-09T23:14", "+1-480-555-0110", 9, """
(silence, then a click)
""", intent="other", urgency=1, root="no-content", team="general", junk="hang-up")
vm("2026-03-10T06:02", "+1-865-555-0102", 44, """
Good morning, this is Ruth Abernathy. I just wanted to say thank you to the young man who helped me last week with
my address, Kevin I think, everything came through fine. You don't need to call me back. Bless you.
""", intent="other", urgency=1, root="compliment", team="general", name="Ruth Abernathy", case_id="FBS-366047")
vm("2026-03-10T06:47", "+1-502-555-0109", 88, """
This is, um, Harold Jennings. My bank closed my old account, they merged with another bank, and I gave you all the new
one, I think, or maybe I didn't. My payment didn't come. Case number... I've got it here... F B S four zero two seven
seven one. Can someone tell me what I need to send? My number is five oh two, five five five, oh one oh nine.
""", intent="direct_deposit_change", urgency=3, root="returned-deposit", team="payments", name="Harold Jennings",
   case_id="FBS-402771")
vm("2026-03-10T07:20", "+1-612-555-0139", 96, """
My name is Patricia Lund, case two nine eight three four four. My March payment has been on hold since February for
what your letter calls an identity check. I have sent everything twice. I've now spoken with my attorney and if this
isn't resolved by the twentieth we are prepared to take legal action. I'd like a call back today, please, at six one
two, five five five, oh one three nine.
""", intent="complaint", urgency=4, root="identity-check-hold", team="correspondence", name="Patricia Lund",
   case_id="FBS-298344", obligations=["legal"])
vm("2026-03-10T07:38", "+1-317-555-0172", 41, """
Hi, Kevin Moore. I got a second one of those twenty-two B letters, the re-verification. I already sent it back in, like,
two weeks ago. Do I have to do it again? It says thirty days or my benefits stop, so. Call me back, please.
""", intent="form_question", urgency=2, root="form-22b-confusion", team="accounts", name="Kevin Moore",
   case_id="FBS-251873", said_case=False, resolvable="status_lookup",
   belief="thinks he must re-send Form 22-B; it was received 2026-03-02 and re-verification is complete")
vm("2026-03-10T07:52", "+1-919-555-0124", 33, """
Darnell Hughes, case three one nine two six six. Was my March payment sent? I didn't see it yet. Thanks.
""", intent="status_payment", urgency=2, root="payment-status", team="payments", name="Darnell Hughes",
   case_id="FBS-319266", resolvable="status_lookup")

# ---------------------------------------------------------------- 8:00 to 9:11
vm("2026-03-10T08:03", "+1-713-555-0146", 63, """
Hello, this is Yolanda Price. You sent me a letter in February asking for a medical statement. My doctor's office says
they faxed it to you on the first. I wanted to check that you got it because I don't want my case closed. My number
is seven one three, five five five, oh one four six. I'm at work until five so after that is best.
""", intent="status_document", urgency=3, root="document-received-confirmation", team="documents",
   name="Yolanda Price", case_id="FBS-284019", said_case=False, window="after 17:00")
vm("2026-03-10T08:16", "+1-702-555-0193", 29, """
Frank Delgado. Where's my payment? It's always on the third. Call me.
""", intent="status_payment", urgency=2, root="payment-date-shift", team="payments", name="Frank Delgado",
   case_id="FBS-133702", said_case=False, resolvable="status_lookup",
   belief="thinks the payment was missed; it's scheduled for 2026-03-12")
vm("2026-03-10T08:29", "+1-202-555-0181", 74, """
Hi, my name is Cheryl Banks, I'm calling about my mother, Edna Banks, she's one of your beneficiaries. I don't have her
case number, I'm sorry. I would like to get copies of, well, everything you have on her. All the letters you've sent,
the notes from her calls, whatever is in her file. She's moving in with me and I'm trying to sort out her paperwork.
My number is two oh two, five five five, oh one eight one.
""", intent="records_request", urgency=3, root="records-request", team="correspondence", name="Cheryl Banks",
   obligations=["records"], said_case=False)
vm("2026-03-10T08:41", "+1-312-555-0155", 36, """
Hi, Teresa Wojcik, case one five oh three nine eight. I moved and sent the address change form last week. Did that go
through? I don't want my mail going to the old place.
""", intent="status_document", urgency=2, root="address-change", team="accounts", name="Teresa Wojcik",
   case_id="FBS-150398", resolvable="status_lookup")
vm("2026-03-10T08:50", "+1-614-555-0168", 92, """
Good morning. My name is Samuel Okafor. My appeal has been pending since January fourteenth and I haven't heard a single
thing. I want you to know I have contacted the office of Congresswoman Alvarez about this and they said they would be
reaching out to you as well. I would appreciate a call back. Case two zero five one one nine.
""", intent="congressional", urgency=4, root="appeal-delay", team="correspondence", name="Samuel Okafor",
   case_id="FBS-205119", obligations=["congressional"])
vm("2026-03-10T08:58", "+1-410-555-0115", 40, """
Hi, this is Bernice Coleman. I sent in the direct deposit form yesterday, well, I dropped it off, the form fourteen.
How long does it take to switch? I want to make sure the next payment goes to the new account.
""", intent="status_document", urgency=2, root="direct-deposit-change", team="accounts", name="Bernice Coleman",
   case_id="FBS-412688", said_case=False, resolvable="status_lookup")
vm("2026-03-10T09:04", "+1-207-555-0133", 58, """
Jim Haskell, case three four five nine oh one. Simple question: I'm going to be in Florida for three months, from
April. Do I need to tell you, or change my address, or what? The website wasn't clear. Thanks. Any time is fine.
""", intent="address_change", urgency=1, root="temporary-address", team="accounts", name="Jim Haskell",
   case_id="FBS-345901")
vm("2026-03-10T09:07", "+1-559-555-0125", 31, """
Hi, um, I'm trying to renew my passport and the website gave me this number? Is this the right place? My name's Josh,
my number's five five nine, five five five, oh one two five.
""", intent="other", urgency=1, root="wrong-agency", team="general", name="Josh")
vm("2026-03-10T09:10", "+1-503-555-0184", 49, """
Hello, Walter Kim, case one eight seven five two oh. I got a letter saying my payment amount is changing in April
because of the cost of living thing. I just want to understand the new amount. Not urgent.
""", intent="form_question", urgency=1, root="cola-letter", team="accounts", name="Walter Kim", case_id="FBS-187520")

# ---------------------------------------------------------------- 9:12 onwards: the sign-in wave begins, mixed with the rest
portal = [
    ("09:12", "+1-216-555-0103", 34, "Hi, I'm trying to log into the portal to upload my form and it keeps saying something went wrong, error E four oh one two. I tried three times. My name is Brenda Sykes."),
    ("09:15", "+1-971-555-0112", 27, "Yeah, the website won't let me in. I put my password in and it just spins and then sends me back to the start. Call me, it's Tom."),
    ("09:19", "+1-480-555-0144", 41, "Hello. I reset my password this morning like it said, and now it says my password is wrong anyway. I typed it very carefully. This is Gloria Mendez, four eight oh, five five five, oh one four four."),
    ("09:22", "+1-608-555-0129", 23, "Your sign-in page is broken. Error 4012. Fix it please."),
    ("09:26", "+1-757-555-0161", 38, "Hi, I'm stuck on the verification code part, it says it sent me a code and nothing comes. I've waited like twenty minutes. Ray Castillo."),
    ("09:29", "+1-646-555-0175", 30, "Morning, I can't get into my account, it says unable to verify identity, please try again later. What does that mean? I need to check my letters."),
    ("09:33", "+1-330-555-0148", 45, "Yes hello, my granddaughter set up the online thing for me and today it won't open. It says, hold on, it says, uh, E dash forty twelve. I don't know what that is. This is Mabel Turner."),
    ("09:36", "+1-913-555-0136", 19, "Login's not working. Kicked out every time. Thanks."),
    ("09:40", "+1-801-555-0119", 52, "Hi there. I've been trying to log in since about nine and the page just goes white after I enter my code. I cleared my cookies, I tried my phone, same thing. I need to submit my income statement today. Priya, P R I Y A, Sharma."),
    ("09:43", "+1-617-555-0187", 33, "Hi, quick one, the portal is saying session expired the second I sign in. Is it me or is it you guys? Dan Whitaker."),
    ("09:47", "+1-503-555-0158", 28, "I keep getting an error when I sign in, something about E four zero one two, and it says to call you. So I'm calling you."),
    ("09:50", "+1-412-555-0114", 47, "Good morning, my name is Hector Ruiz. I wanted to upload the document your letter asked for, but I cannot get past the login. It says something went wrong. Is there another way I can send it? Mail? Fax?"),
    ("09:54", "+1-919-555-0166", 35, "Hello, the sign-in keeps asking me for the code again and again, like in a loop. I put the code in and it asks for another one. Monica."),
    ("09:57", "+1-205-555-0121", 26, "Can't log in. Error. Please call back. Five five five oh one two one, area code two oh five."),
    ("10:01", "+1-585-555-0140", 39, "Hi, I'm locked out of my account? It said too many attempts but I only tried twice and it was right both times. This is Courtney Hall."),
    ("10:05", "+1-775-555-0152", 31, "Yes, I'm trying to see my payment history on your website and it won't let me sign in. Is something going on today?"),
    ("10:08", "+1-714-555-0131", 58, "Xin chào, tôi là Trần Linh, số hồ sơ ba bảy bảy không một bốn. Tôi không đăng nhập vào trang web được, nó báo lỗi E bốn không một hai. Tôi cần xem thư của tôi. Xin gọi lại cho tôi. Cảm ơn."),
    ("10:12", "+1-860-555-0109", 24, "Website down? Can't sign in. Error four zero one two. Bye."),
    ("10:16", "+1-215-555-0137", 44, "Hello, I'm sorry to bother you, I'm not very good with computers but I am trying to sign in and it keeps saying unable to verify. Did I do something wrong? My name is Agnes Kowalski."),
]
portal2 = [
    ("10:22", "+1-937-555-0127", 36, "Hey, it's Brian. Your login is giving me error 4012 since this morning. I need to update my bank info before Friday."),
    ("10:31", "+1-651-555-0170", 29, "Hi, I can't access the portal, it just loops back to the sign-in screen after the verification step. Please advise."),
    ("10:44", "+1-402-555-0118", 40, "Hello, I am calling because the online account is not working for me. I put in my information and it says try again later. I have tried again later, many times! Ha. Please call me. Ines Moreau."),
    ("10:52", "+1-571-555-0193", 22, "Sign in broken. E-4012. Thanks."),
    ("11:12", "+1-385-555-0141", 33, "Hi, my wife and I both can't get into our accounts this morning, same error, something went wrong E four oh one two. Is there a problem with the system? Paul Jensen."),
    ("11:25", "+1-303-555-0116", 37, "I've tried the website on two computers. Same message: we couldn't verify your sign-in. Can you look into it? I need my tax form."),
    ("11:41", "+1-516-555-0134", 26, "Yeah, your portal won't take my code. Says expired every time even though I use it right away. Call me back."),
    ("12:03", "+1-405-555-0150", 30, "Hello, I've been trying since nine thirty this morning to log in. It doesn't work. What is going on? Call me please."),
    ("12:18", "+1-262-555-0164", 34, "Hi, still can't sign in, been trying all morning. Same thing every time, it gets to the code and then says something went wrong. Is anybody working on this? Thanks, it's Nora."),
]

times = [t for t, *_ in portal]
for t, phone, dur, text in portal:
    viet = phone == "+1-714-555-0131"
    vm(f"2026-03-10T{t}", phone, dur, text, **PORTAL, urgency=2, lang="vi" if viet else "en",
       name="Linh Tran" if viet else None, case_id="FBS-377014" if viet else None,
       gist=("Can't sign in to the website; it shows error E4012. Needs to read their letters. Asks for a call back."
             if viet else None))
    if t == "09:47":   # a status question in between: answerable from the case system
        vm("2026-03-10T09:48", "+1-206-555-0177", 66, """
Kumusta po, ako po si Rosario Dimaculangan. Nakatanggap po ako ng sulat tungkol sa Form 22-B. Ipinadala ko na po iyon
noong Pebrero. Kailangan ko pa po bang magpadala ulit? Natatakot po ako na mahinto ang aking benepisyo. Salamat po.
""", intent="form_question", urgency=2, root="form-22b-confusion", team="accounts", lang="tl",
           name="Rosario Dimaculangan", case_id="FBS-266533", said_case=False, resolvable="status_lookup",
           gist="Got a letter about Form 22-B; already sent it in February. Asks whether she must send it again; afraid her benefits will stop.",
           belief="fears she must re-send Form 22-B; it was received 2026-02-25")
    if t == "10:16":   # the repeat caller's third message
        vm("2026-03-10T10:19", "+1-614-555-0142", 83, """
This is the THIRD time I'm calling. Dolores Whitfield. Nobody has called me back. I sent your form, I sent it in February,
and you're holding my money. My rent was due on the first. I've been a customer, or whatever you call it, for eleven years
and I have never been treated like this. One oh four two two seven. Call me. Today.
""", intent="complaint", urgency=4, root="form-22b-confusion", team="accounts", name="Dolores Whitfield",
           case_id="FBS-104227", linked=["m01", "m03"])
        vm("2026-03-10T10:27", "+1-210-555-0158", 54, """
Hola, habla Carmen Reyes. I sent the change of address, the form nine, el sábado. Quería saber si ya lo recibieron porque
me voy a mudar el quince y no quiero que se pierda mi cheque. Gracias, my number is the one I'm calling from.
""", intent="status_document", urgency=2, root="address-change", team="accounts", lang="es-en",
           name="Carmen Reyes", case_id="FBS-170266", said_case=False, resolvable="status_lookup",
           gist="Sent the change-of-address form (Form 9) on Saturday; asks whether it arrived, since she moves on the 15th and doesn't want her check lost.")

for t, phone, dur, text in portal2:
    vm(f"2026-03-10T{t}", phone, dur, text, **PORTAL, urgency=2)
    if t == "10:52":   # the buried urgent one (10:04, so position 37 in the chronological inbox)
        vm("2026-03-10T10:04", "+1-865-555-0190", 141, """
Hi, um, hello. My name is Eleanor Voss, I'm, um, I'm seventy-eight and I've never had to call about anything before so I
hope this is the right number. I'm calling about my payment, the March one, it didn't come, and I called my bank and they
said nothing came in. And I don't, I'm not sure what happened. I did get a letter, I think, about my bank, or maybe that was
from the bank. Anyway. The reason I'm calling is the electric company sent me a notice and they're going to shut off my
power on Friday if I don't pay, and it's still cold at night here, and I, I have my oxygen machine that needs the power. So
I'm a little worried. My daughter usually helps me but she's in the hospital right now. My number is eight six five, five
five five, oh one, nine oh. Eight six five, five five five, oh one nine zero. Thank you, I'm sorry for the long message.
""", intent="urgent_hardship", urgency=5, root="returned-deposit", team="escalations", name="Eleanor Voss",
           case_id="FBS-366098", said_case=False, obligations=["welfare"])
    if t == "11:12":
        vm("2026-03-10T11:18", "+1-505-555-0187", 35, """
Angela Ruiz, two two four four one seven. My payment is late. It's always the third. Is it coming or not? Thanks.
""", intent="status_payment", urgency=2, root="payment-date-shift", team="payments", name="Angela Ruiz",
           case_id="FBS-224417", resolvable="status_lookup",
           belief="thinks the payment was missed; it's scheduled for 2026-03-12")
    if t == "11:25":
        vm("2026-03-10T11:33", "+1-423-555-0106", 79, """
Hi, my name is Denise Carter. I'm calling about my neighbor, Mr. Albert Price, he's on your benefits. I'm worried about him.
He told me his money stopped coming and he hasn't been eating much, and yesterday he seemed really confused, he didn't
know what day it was. He lives alone. I don't know who else to call. I'm at four two three, five five five, oh one oh six.
""", intent="welfare", urgency=5, root="welfare-concern", team="escalations", name="Denise Carter",
           obligations=["welfare"], said_case=False)
    if t == "11:41":
        vm("2026-03-10T11:49", "+1-859-555-0183", 70, """
Yes, good morning, this is Raymond Ellis. I'm calling because my senator's caseworker, Ms. Patel in Senator Brooks'
office, asked me to call and get an update on my claim and she said she'd be following up with you directly. I filed back
in December. Case three oh eight five five two. Thank you.
""", intent="congressional", urgency=4, root="claim-delay", team="correspondence", name="Raymond Ellis",
           case_id="FBS-308552", obligations=["congressional"])

# ---------------------------------------------------------------- the afternoon
vm("2026-03-10T12:41", "+1-314-555-0178", 63, """
Hi there, I got this letter, the twenty-two B, it says I have to re-verify within thirty days or my benefits could be
suspended. Re-verify what? My address? My income? It doesn't really say. And it says enclosed form but there's nothing
enclosed, just the letter. I'm a little nervous about it. Terrence Gibbs, three one four, five five five, oh one seven eight.
""", intent="form_question", urgency=2, root="form-22b-confusion", team="accounts", name="Terrence Gibbs")
vm("2026-03-10T13:20", "+1-252-555-0128", 46, """
Hi, I need to change my phone number on file, the old one is disconnected. The new one is two five two, five five five,
oh one two eight. My name is Lisa Grant. Case one nine nine four seven three. Mornings before ten are best.
""", intent="address_change", urgency=1, root="contact-info-change", team="accounts", name="Lisa Grant",
   case_id="FBS-199473", window="before 10:00")
vm("2026-03-10T13:47", "+1-334-555-0135", 33, """
Hello, can I fax the medical form instead of mailing it? And if I can, what's the fax number? The letter only has a
mailing address. This is Gwen Porter. Thanks so much.
""", intent="form_question", urgency=1, root="document-submission-method", team="documents", name="Gwen Porter")
vm("2026-03-10T15:12", "+1-563-555-0151", 118, """
Yeah, hi, this is, uh, Douglas, Doug Brenner, I got a letter that says I was overpaid, overpaid in, um, was it January?
No, wait, December and January, and they want, it says I owe four hundred, no, sorry, four thousand two hundred and, uh,
sixty dollars, which, I don't have that, obviously. And I don't understand how I was overpaid because nothing changed,
I didn't, I mean my hours went up a little at the hardware store but I reported that, I'm pretty sure I reported it.
So I don't know if I'm supposed to appeal it or what. The letter has a, a number on it, O P dash two oh two six dash, uh,
I can't read the rest. Five six three, five five five, oh one five one. I'm off after three thirty most days.
""", intent="overpayment", urgency=3, root="overpayment-notice", team="payments", name="Doug Brenner",
   window="after 15:30")
vm("2026-03-10T14:05", "+1-865-555-0102", 38, """
Ruth Abernathy again, I'm so sorry, I forgot to ask this morning. Is my payment still the third of the month after my
address change? That's all. Thank you dear.
""", intent="status_payment", urgency=1, root="payment-status", team="payments", name="Ruth Abernathy",
   case_id="FBS-366047", said_case=False, resolvable="status_lookup")

# the cases only mentioned (no backend facts needed beyond existence)
case("FBS-366098", "Eleanor Voss", "+1-865-555-0190", status="payment returned by bank",
     payments=[("2026-03-03", 905.00, "returned: account number invalid")],
     last="2026-03-05 deposit returned", team="payments", region="TN")
case("FBS-308552", "Raymond Ellis", "+1-859-555-0183", status="claim pending",
     last="2025-12-08 claim filed", team="correspondence", region="KY")
case("FBS-199473", "Lisa Grant", "+1-252-555-0128", status="active", last="2026-02-02 payment issued",
     team="accounts", region="NC")

# ---------------------------------------------------------------- order, ids, links, checks
M.sort(key=lambda m: m["receivedAt"])
for i, m in enumerate(M, 1):
    m["id"] = f"m{i:02d}"
ids = {m["receivedAt"] + m["callerId"]: m["id"] for m in M}
whit = [m["id"] for m in M if m["truth"]["callerName"] == "Dolores Whitfield"]
for m in M:
    if m["truth"]["callerName"] == "Dolores Whitfield":
        m["truth"]["linkedTo"] = [x for x in whit if x != m["id"]]
tr = [m["truth"] for m in M]
assert len(M) == 60, len(M)
assert M[36]["truth"]["urgency"] == 5 and M[36]["truth"]["callerName"] == "Eleanor Voss", M[36]["id"]
assert sum(t["group"] == "portal-sign-in" for t in tr) == 28
assert min(m["receivedAt"] for m in M if m["truth"]["group"]) == "2026-03-10T09:12"
assert not any("outage" in m["script"].lower() for m in M)
assert sorted(m["lang"] for m in M if m["lang"] != "en") == ["es", "es-en", "tl", "vi"]
assert len(whit) == 3
obl = sorted(o for t in tr for o in t["obligations"])
assert obl.count("congressional") == 2 and obl.count("records") == 1 and obl.count("legal") == 1 and "welfare" in obl, obl
assert sum(t["resolvableBy"] == "status_lookup" for t in tr) == 12, sum(t["resolvableBy"] == "status_lookup" for t in tr)
missing = [t for t in tr if not t["caseNumberSaid"] and t["caseId"] and t["caseId"] in CASES]
assert len(missing) >= 6, len(missing)
for t in tr:
    assert not t["caseId"] or t["caseId"] in CASES, t["caseId"]

# ---------------------------------------------------------------- junk: twice as much as the real calls, generated
# Robocalls and scams run a minute or more (so listening to them is real work in Mode 0); silence, hang-ups and
# pocket dials are quick or muffled. Some robocalls come word for word from many numbers; a few come from numbers
# already on the blocked list; the rest have to be judged.
rng = random.Random(2026)
ROBO = [
    ("This is an important message about your vehicle's extended warranty. Our records show your coverage is about "
     "to expire. To speak with a specialist about extending your coverage, press one now. To be removed from our "
     "list, press two.", (55, 75)),
    ("Congratulations! You have been selected to receive a free three-night cruise to the Bahamas. This offer "
     "expires today. Press one to claim your prize before it's given to another caller.", (45, 60)),
    ("Hello, this is a final notice regarding your credit card account. You qualify for a lower interest rate. "
     "Press one to speak with an account specialist now. This is not a sales call.", (50, 65)),
    ("This call is to inform you that your social security number has been suspended due to suspicious activity. "
     "To avoid legal consequences, press one immediately to speak with an officer.", (40, 55)),
]
ROBO_VARIANTS = [
    "Hi there, we noticed you might be paying too much for your electricity. Our energy advisors can cut your bill "
    "in half with a new solar program, at no cost to you. Call us back at your convenience to learn more.",
    "Good afternoon, I'm calling on behalf of the Home Improvement Grants office. Homeowners in your area may be "
    "eligible for a free roof inspection and replacement. Call us back to schedule your appointment.",
    "This is Rachel from customer services. We've been trying to reach you about the warranty on your home "
    "appliances. Please return our call so we can keep your protection active.",
    "Hello, you've been pre-approved for a business loan of up to fifty thousand dollars with no credit check. "
    "Call us back today, this approval is only good for twenty-four hours.",
    "We are reaching out regarding a package that could not be delivered to your address. Please call back with "
    "your tracking details so we can reschedule the delivery.",
]
WRONG = ["Hey Mike, it's me. Call me back about Saturday, okay? Bye.",
         "Hi Mom, it's Jess. I'm running late, I'll pick up the kids at five. Love you.",
         "Yeah, this is Tony from the shop, your truck's ready whenever you want to swing by.",
         "Hi, is this the pizza place on Fourth? I wanted to change my order. Hello? Oh, sorry, wrong number."]
QUIET = [("(silence)", "silence", (4, 20)), ("(a click)", "hang-up", (1, 5)), ("(silence, then a dial tone)", "hang-up", (6, 15)),
         ("(muffled voices, rustling, traffic noise)", "pocket-dial", (30, 90)),
         ("(a television in the background, then rustling)", "pocket-dial", (25, 70))]
BLOCKED = ["+1-202-555-0199", "+1-212-555-0183", "+1-305-555-0177"]   # also in data/blocked_numbers.json


def junk_number():
    return f"+1-{rng.choice(['201', '312', '415', '469', '503', '602', '646', '702', '786', '818', '904', '972'])}-555-0{rng.randint(100, 199)}"


def junk_time():
    if rng.random() < 0.35:            # yesterday evening and overnight
        mins = rng.randint(17 * 60, 23 * 60 + 59)
        return f"2026-03-09T{mins // 60:02d}:{mins % 60:02d}"
    mins = rng.randint(0, 16 * 60 + 15)
    return f"2026-03-10T{mins // 60:02d}:{mins % 60:02d}"


J = []
plan = ["robo"] * 52 + ["variant"] * 20 + ["blocked"] * 8 + ["wrong"] * 14 + ["quiet"] * 26
for kind in plan:
    if kind in ("robo", "blocked"):
        script, (lo, hi) = rng.choice(ROBO)
        label, phone = "robocall", (rng.choice(BLOCKED) if kind == "blocked" else junk_number())
    elif kind == "variant":
        script, (lo, hi), label, phone = rng.choice(ROBO_VARIANTS), (35, 60), "scam", junk_number()
    elif kind == "wrong":
        script, (lo, hi), label, phone = rng.choice(WRONG), (8, 25), "wrong-number", junk_number()
    else:
        script, label, (lo, hi) = rng.choice(QUIET)
        phone = junk_number()
    J.append({"receivedAt": junk_time(), "callerId": phone, "durationSec": rng.randint(lo, hi), "lang": "en",
              "script": script,
              "truth": {"intent": "other", "urgency": 1, "rootCause": "junk", "team": "general", "callerName": None,
                        "callbackNumber": phone, "caseId": None, "caseNumberSaid": False, "group": None,
                        "obligations": [], "resolvableBy": None, "linkedTo": [], "callbackWindow": None,
                        "beliefMismatch": None, "englishGist": None, "junk": label}})
J.sort(key=lambda m: (m["receivedAt"], m["callerId"]))
for i, m in enumerate(J, 1):
    m["id"] = f"j{i:03d}"
# Real calls that look like junk (a few words, a bad line): they must reach a person
for m in M:
    m["truth"]["looksLikeJunk"] = not m["truth"]["junk"] and len(m["script"].split()) <= 10
assert len(J) == 120
assert sum(not m["truth"]["junk"] for m in M) == 59 and sum(1 for m in M + J if m["truth"]["junk"]) == 121
assert sum(m["truth"]["looksLikeJunk"] for m in M) >= 3, [m["script"] for m in M if m["truth"]["looksLikeJunk"]]
OUT.write_text(json.dumps({"date": "2026-03-10", "voicemails": M + J, "cases": sorted(CASES.values(), key=lambda c: c["id"])},
                          indent=1, ensure_ascii=False) + "\n")
print(f"wrote {OUT.name}: {len(M) + len(J)} voicemails ({len(J)} generated junk), {len(CASES)} cases; urgent at {M[36]['id']}; "
      f"{len(missing)} without a case number said but findable by caller ID")
