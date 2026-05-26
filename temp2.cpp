#include <bits/stdc++.h>
using namespace std;

struct User {
    string name;
    int budget, energy;
    set<string> tags;
    bool active = true;
};

struct Activity {
    int id;
    string name;
    int cost, duration, energy;
    string tag;
};

struct ParsedEvent {
    string type, name, tag, raw;
    int day, value;
};

struct Input {
    int N, D, H;
    vector<User> users;
    map<int, Activity> activities;
    vector<string> events;
};

static Input readInput() {
    Input in;
    cin >> in.N >> in.D >> in.H;
    in.users.resize(in.N);
    for (int i = 0; i < in.N; i++) {
        int k;
        cin >> in.users[i].name >> in.users[i].budget >> in.users[i].energy >> k;
        for (int j = 0; j < k; j++) { string t; cin >> t; in.users[i].tags.insert(t); }
        in.users[i].active = true;
    }
    int A; cin >> A;
    for (int i = 0; i < A; i++) {
        Activity a;
        cin >> a.id >> a.name >> a.cost >> a.duration >> a.energy >> a.tag;
        in.activities[a.id] = a;
    }
    int E; cin >> E;
    cin.ignore();
    for (int i = 0; i < E; i++) {
        string line;
        getline(cin, line);
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
        in.events.push_back(line);
    }
    return in;
}

static string formatDay(int day, vector<int> ids, int cost, int sat) {
    if (ids.empty())
        return "Day " + to_string(day) + ": REST | cost=0 satisfaction=0";
    sort(ids.begin(), ids.end());
    string s = "Day " + to_string(day) + ": ";
    for (size_t i = 0; i < ids.size(); i++) { if (i) s += ' '; s += to_string(ids[i]); }
    s += " | cost=" + to_string(cost) + " satisfaction=" + to_string(sat);
    return s;
}

ParsedEvent parseEvent(const string& line) {
    ParsedEvent e; e.raw = line; e.value = 0;
    istringstream ss(line);
    ss >> e.type >> e.day;
    if      (e.type == "WEATHER")                 { ss >> e.tag; }
    else if (e.type == "DROP")                    { ss >> e.name; }
    else if (e.type == "FATIGUE" || e.type == "BUDGET") { ss >> e.name >> e.value; }
    return e;
}

struct DayResult { vector<int> ids; int cost, sat; };

DayResult planDay(const vector<User>& initUsers,
                  const vector<ParsedEvent>& applied,
                  const map<int, Activity>& activities,
                  const set<int>& usedIds,
                  int day, int H) {

    // Build effective user state for this day
    vector<User> users = initUsers;
    for (auto& e : applied) {
        if (e.type == "DROP"    && e.day <= day) { for (auto& u : users) if (u.name == e.name) u.active = false; }
        if (e.type == "FATIGUE" && e.day <= day) { for (auto& u : users) if (u.name == e.name) u.energy = e.value; }
        if (e.type == "BUDGET"  && e.day <= day) { for (auto& u : users) if (u.name == e.name) u.budget = e.value; }
    }

    vector<User*> active;
    for (auto& u : users) if (u.active) active.push_back(&u);
    if (active.empty()) return {{}, 0, 0};

    int minBudget = INT_MAX, minEnergy = INT_MAX;
    for (auto u : active) { minBudget = min(minBudget, u->budget); minEnergy = min(minEnergy, u->energy); }

    // Weather blocks for this specific day
    set<string> blocked;
    for (auto& e : applied) if (e.type == "WEATHER" && e.day == day) blocked.insert(e.tag);

    // Build eligible list (map is ordered by id)
    vector<pair<int, const Activity*>> elig;
    for (auto& [id, act] : activities) {
        if (usedIds.count(id) || blocked.count(act.tag)) continue;
        elig.push_back({id, &act});
    }
    int k = (int)elig.size();

    // Start with empty set as best (→ REST if nothing better found)
    int bestSat = 0, bestCost = 0;
    vector<int> bestIds;

    for (int mask = 1; mask < (1 << k); mask++) {
        int totCost = 0, totEnergy = 0, totDur = 0, sat = 0;
        vector<int> ids;
        for (int i = 0; i < k; i++) {
            if (!(mask & (1 << i))) continue;
            auto& act = *elig[i].second;
            totCost   += act.cost;
            totEnergy += act.energy;
            totDur    += act.duration;
            for (auto u : active) if (u->tags.count(act.tag)) sat++;
            ids.push_back(elig[i].first);
        }
        if (totCost > minBudget || totEnergy > minEnergy || totDur > H) continue;

        sort(ids.begin(), ids.end());

        // Lexicographic tuple comparison: (-sat, cost, ids)
        bool better = false;
        if      (sat > bestSat)                        better = true;
        else if (sat == bestSat && totCost < bestCost) better = true;
        else if (sat == bestSat && totCost == bestCost && ids < bestIds) better = true;

        if (better) { bestSat = sat; bestCost = totCost; bestIds = ids; }
    }

    return {bestIds, bestCost, bestSat};
}

static string solve(Input in) {
    string out;

    vector<ParsedEvent> parsedEvents;
    for (auto& line : in.events) parsedEvents.push_back(parseEvent(line));

    vector<DayResult> plan(in.D + 1);
    set<int> used;
    vector<ParsedEvent> applied;

    // Plan days [startDay..D] sequentially, building on current `used`
    auto runPlan = [&](int startDay) {
        for (int d = startDay; d <= in.D; d++) {
            plan[d] = planDay(in.users, applied, in.activities, used, d, in.H);
            for (int id : plan[d].ids) used.insert(id);
        }
    };

    // Initial full plan
    runPlan(1);
    out += "=== PLAN ===\n";
    for (int d = 1; d <= in.D; d++)
        out += formatDay(d, plan[d].ids, plan[d].cost, plan[d].sat) + "\n";

    // Process events in order
    for (int i = 0; i < (int)parsedEvents.size(); i++) {
        auto& e = parsedEvents[i];
        out += "=== EVENT " + to_string(i + 1) + ": " + e.raw + " ===\n";

        applied.push_back(e);

        // Freeze days 1..e.day-1; rebuild used from those frozen days
        used.clear();
        for (int d = 1; d < e.day; d++)
            for (int id : plan[d].ids) used.insert(id);

        // Replan from event's day onward
        runPlan(e.day);

        // Output only replanned days
        for (int d = e.day; d <= in.D; d++)
            out += formatDay(d, plan[d].ids, plan[d].cost, plan[d].sat) + "\n";
    }

    return out;
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    Input in = readInput();
    cout << solve(in);
    return 0;
}