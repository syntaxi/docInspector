import json
from datetime import datetime

from httplib2 import Http
from oauth2client import file, client, tools


class ChangeData:
    def __init__(self, data):
        self.startChar = data['si']
        self.endChar = data['ei']
        self.editType = data['sm']['revdiff_dt']
        self.editType = data['sm']['revdiff_dt'] if "revdiff_dt" in data['sm'] else None
        self.user = data['sm']['revdiff_aid'] if "revdiff_aid" in data['sm'] else "Anonymous"

    def isValid(self):
        return self.editType and self.user

    def getSize(self):
        return self.endChar - self.startChar


class RevisionData:
    def __init__(self, data, requester):
        self.startId = data['start']
        self.endId = data['end']
        self.endTime = data['endMillis']
        self.users = data['users']
        self.name = data['name'] if 'name' in data else "unnamed"
        self.revisionKey = data['revisionMac']
        self.hasSubRevisions = data['expandable']
        self.changes = None
        self.requester = requester

    def __str__(self):
        return f"'{self.name}' revision @ {datetime.fromtimestamp(1347517370).strftime('%c')}"

    def getChanges(self):
        if not self.changes:
            self.changes = []
            data = self.requester.requestRevision(self)
            for chunk in data['chunkedSnapshot']:
                for entry in chunk:
                    if entry['ty'] == 'as' and entry['st'] == "revision_diff":
                        self.changes.append(ChangeData(entry))

            self.changes = [change for change in self.changes if change.isValid()]

        return self.changes


class UnsafeRequester:
    def __init__(self, http, docId):
        self.http = http
        self.docId = docId

    def requestRevision(self, revision):
        (_, content) = self.http.request(
            f"https://docs.google.com/document/d/{self.docId}/"
            f"showrevision?id={self.docId}&"
            f"end={revision.endId}&start={revision.startId}&"
            f"smv=4&srfn=false&ern=false&"
            f"includes_info_params=true")
        return json.loads(content[5:])

    def requestList(self):
        (_, content) = self.http.request(f"https://docs.google.com/document/d/{self.docId}/revisions/"
                                         f"tiles?id={self.docId}&"
                                         f"start=1&"
                                         f"showDetailedRevisions=false&filterNamed=false&"
                                         f"ouid=107477822689043550957&includes_info_params=true")
        return json.loads(content[5:])


class User:
    def __init__(self, userId, data):
        self.id = userId
        self.name = data['name']
        self.photo = data['photo']
        self.color = data['color']
        self.anonymous = data['anonymous']


class RevisionList(list):
    def __init__(self, data, requester):
        self.startRevision = data['firstRev']
        revisions = []
        self.iterId = 0
        self.requester = requester
        for revision in data['tileInfo']:
            revisions.append(RevisionData(revision, self.requester))
        super().__init__(revisions)

    def __str__(self):
        return f"[{', '.join([str(revision) for revision in self])}]"


class Document:
    def __init__(self, http, docId):
        self.requester = UnsafeRequester(http, docId)
        self.docId = docId
        self.revisions = None

    def listRevisions(self):
        if not self.revisions:
            content = self.requester.requestList()
            self.revisions = RevisionList(content, self.requester)
        return self.revisions


def main():
    store = file.Storage('token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', "https://www.googleapis.com/auth/drive")
        creds = tools.run_flow(flow, store)

    http = creds.authorize(Http())
    document = Document(http, "1DN4LxL8nSd9ZUbqhpXIfasmm8PQykJonOw7nUpKXpoo")

    revisions = document.listRevisions()
    print(f"There are {len(revisions)} revisions in this document")
    for revision in revisions:
        print(f"\t{str(revision)}:")
        editors = {}
        changes = revision.getChanges()
        for change in changes:
            if change.user not in editors:
                editors[change.user] = [change.user, 0, 0, 0]
            editors[change.user][1] += 1
            if change.editType == 1:
                editors[change.user][2] += change.getSize()
            elif change.editType == 2:
                editors[change.user][3] += change.getSize()
        print(f"\t\tThere were {len(editors)} editors:")
        for editor in editors.values():
            print(f"\t\t{editor[0]} made {editor[1]} edits, totaling {editor[2]} additions and {editor[3]} deletions")


if __name__ == '__main__':
    main()
