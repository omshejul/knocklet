# Knocklet

Knocklet imports people for LinkedIn outreach and records the actions taken for them.

## Language

**Person**:
A LinkedIn member known to the app, identified by a normalized public profile ID.
_Avoid_: Contact, lead, CSV row

**Import Batch**:
One uploaded file and the rows discovered in it.
_Avoid_: Campaign, list

**Import Row**:
One source row from an Import Batch. It records what was supplied, even when the Person already exists.
_Avoid_: Person, connection request

**Invitation**:
The connection invitation lifecycle for a Person, including whether it is pending, accepted, or needs review.
_Avoid_: Import Row, request

**Message Template**:
User-approved text that may be rendered into a follow-up message.
_Avoid_: Message, script

**Message**:
One follow-up intended for a Person after an Invitation is accepted. Its text does not change when its Message Template changes later.
_Avoid_: Template, reply

**Work Item**:
A durable record of an Invitation check, Invitation send, acceptance check, or Message send that the app should perform.
_Avoid_: Thread, background task
