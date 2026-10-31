"""The data model, shared by the API and the pipeline. Raw input, ground truth and (later) AI output are kept
apart, so any mode can be re-run and any AI field scored against the truth."""

from typing import Literal

from pydantic import BaseModel

Obligation = Literal["congressional", "records", "legal", "welfare", "discrimination"]


class Truth(BaseModel):
    intent: str
    urgency: int
    rootCause: str
    team: str
    callerName: str | None = None
    callbackNumber: str
    caseId: str | None = None
    caseNumberSaid: bool = True
    group: str | None = None
    obligations: list[Obligation] = []
    resolvableBy: str | None = None
    linkedTo: list[str] = []
    callbackWindow: str | None = None
    beliefMismatch: str | None = None
    englishGist: str | None = None


class Voicemail(BaseModel):
    id: str
    receivedAt: str
    callerId: str
    durationSec: int
    lang: str
    script: str
    truth: Truth


class Payment(BaseModel):
    date: str
    amount: float
    status: str


class Doc(BaseModel):
    name: str
    received: str | None = None


class Case(BaseModel):
    id: str
    name: str
    phone: str
    status: str
    region: str
    lang: str = "en"
    payments: list[Payment] = []
    docs: list[Doc] = []
    lastAction: str
    team: str


class Event(BaseModel):
    id: str
    date: str
    type: Literal["mailing", "release", "policy", "payment-shift"]
    name: str
    description: str


class Promise(BaseModel):
    text: str
    dueAt: str
    kept: bool | None = None


class Contact(BaseModel):
    id: str
    caseId: str
    at: str
    channel: Literal["voicemail", "phone", "web"]
    rootCause: str
    lang: str
    region: str
    handleMin: float
    resolved: bool
    daysToResolve: int | None = None
    text: str
    promise: Promise | None = None


class KBArticle(BaseModel):
    id: str
    title: str
    body: str
    topics: list[str]
