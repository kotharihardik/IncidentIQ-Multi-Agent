// JSON -> TypeScript Type Generator
// Handles all edge cases per problem spec.

#include <bits/stdc++.h>
using namespace std;

// ─── minimal JSON parser ───────────────────────────────────────────────────
struct JVal {
    enum Kind { Null, Bool, Num, Str, Arr, Obj } kind;
    bool   b{};
    double n{};
    string s;
    vector<JVal>                    arr;
    vector<pair<string,JVal>>       obj; // preserve order for parsing; we sort later
};

static void skipWS(const string& t, size_t& i){
    while(i<t.size() && (t[i]==' '||t[i]=='\t'||t[i]=='\n'||t[i]=='\r')) i++;
}
static string parseStr(const string& t, size_t& i){
    // i points to opening "
    i++; // skip "
    string r;
    while(i<t.size() && t[i]!='"'){
        if(t[i]=='\\'){
            i++;
            char c=t[i++];
            switch(c){
                case '"': r+='"'; break;
                case '\\': r+='\\'; break;
                case '/': r+='/'; break;
                case 'b': r+='\b'; break;
                case 'f': r+='\f'; break;
                case 'n': r+='\n'; break;
                case 'r': r+='\r'; break;
                case 't': r+='\t'; break;
                case 'u':{
                    // 4 hex digits – simplified: just skip or keep as-is
                    string hex=t.substr(i,4); i+=4;
                    unsigned cp=stoul(hex,nullptr,16);
                    if(cp<0x80) r+=(char)cp;
                    else if(cp<0x800){r+=(char)(0xC0|(cp>>6));r+=(char)(0x80|(cp&0x3F));}
                    else{r+=(char)(0xE0|(cp>>12));r+=(char)(0x80|((cp>>6)&0x3F));r+=(char)(0x80|(cp&0x3F));}
                    break;
                }
                default: r+=c;
            }
        } else {
            r+=t[i++];
        }
    }
    i++; // skip closing "
    return r;
}
static JVal parseVal(const string& t, size_t& i);
static JVal parseObj(const string& t, size_t& i){
    JVal v; v.kind=JVal::Obj;
    i++; // skip {
    skipWS(t,i);
    while(i<t.size()&&t[i]!='}'){
        string key=parseStr(t,i);
        skipWS(t,i); i++; // skip :
        skipWS(t,i);
        JVal val=parseVal(t,i);
        v.obj.push_back({key,move(val)});
        skipWS(t,i);
        if(i<t.size()&&t[i]==','){i++;skipWS(t,i);}
    }
    i++; // skip }
    return v;
}
static JVal parseArr(const string& t, size_t& i){
    JVal v; v.kind=JVal::Arr;
    i++; // skip [
    skipWS(t,i);
    while(i<t.size()&&t[i]!=']'){
        v.arr.push_back(parseVal(t,i));
        skipWS(t,i);
        if(i<t.size()&&t[i]==','){i++;skipWS(t,i);}
    }
    i++; // skip ]
    return v;
}
static JVal parseVal(const string& t, size_t& i){
    skipWS(t,i);
    char c=t[i];
    if(c=='"') { JVal v; v.kind=JVal::Str; v.s=parseStr(t,i); return v; }
    if(c=='{') return parseObj(t,i);
    if(c=='[') return parseArr(t,i);
    if(c=='n'){ i+=4; JVal v; v.kind=JVal::Null; return v; }
    if(c=='t'){ i+=4; JVal v; v.kind=JVal::Bool; v.b=true; return v; }
    if(c=='f'){ i+=5; JVal v; v.kind=JVal::Bool; v.b=false; return v; }
    // number
    size_t j=i;
    while(j<t.size()&&(t[j]=='-'||t[j]=='+'||t[j]=='.'||isdigit(t[j])||t[j]=='e'||t[j]=='E')) j++;
    JVal v; v.kind=JVal::Num; v.n=stod(t.substr(i,j-i)); i=j; return v;
}

// ─── Type tree ────────────────────────────────────────────────────────────
// We represent the merged type tree as a tree of "TypeNode" per interface path.
// Each interface node has a map of field_name -> FieldInfo.

struct FieldInfo;
struct InterfaceNode {
    // key -> FieldInfo
    map<string,FieldInfo*> fields; // sorted by key (map is ordered)
    int totalObjects = 0; // how many objects merged into this node
};

struct FieldInfo {
    bool optional = false;
    // observed primitive/null types
    set<string> primitiveTypes; // "string","number","boolean","null"
    // array info
    bool hasArray = false;
    // elements of all arrays for this field
    set<string> arrayElemPrimitives;
    bool arrayHasObjects = false;
    InterfaceNode* arrayObjNode = nullptr; // interface for array element objects
    // object info
    bool hasObject = false;
    InterfaceNode* objectNode = nullptr; // interface for direct object
    // counts for optionality: how many objects had this key present
    int presentCount = 0;
};

// Global interface registry
struct InterfaceRecord {
    string baseName;   // e.g. "Address"
    string finalName;  // after collision resolution e.g. "Address2"
    InterfaceNode* node;
};

// We'll collect all interfaces in DFS order (for name assignment)
// then sort by finalName for output.

// ─── Main logic ───────────────────────────────────────────────────────────

// We do everything in a single pass builder.

struct Builder {
    // Maps from InterfaceNode* to its record
    map<InterfaceNode*, InterfaceRecord*> nodeToRecord;
    vector<InterfaceRecord*> allRecords; // in DFS encounter order
    set<string> usedNames;

    InterfaceNode* root = nullptr;
    string rootName;

    // pool for nodes and fields and records
    vector<unique_ptr<InterfaceNode>> nodes;
    vector<unique_ptr<FieldInfo>> fieldPool;
    vector<unique_ptr<InterfaceRecord>> recordPool;

    InterfaceNode* newNode(){
        nodes.push_back(make_unique<InterfaceNode>());
        return nodes.back().get();
    }
    FieldInfo* newField(){
        fieldPool.push_back(make_unique<FieldInfo>());
        return fieldPool.back().get();
    }

    // Merge a JSON object into an InterfaceNode
    void mergeObj(InterfaceNode* node, const JVal& obj){
        node->totalObjects++;
        set<string> keysPresent;
        for(auto& [k,v]: obj.obj){
            keysPresent.insert(k);
            FieldInfo*& fi = node->fields[k];
            if(!fi) fi=newField();
            mergeVal(fi, k, v);
        }
        // Mark absent keys optional
        for(auto& [k,fi]: node->fields){
            if(!keysPresent.count(k)){
                fi->optional=true;
            }
        }
    }

    void mergeVal(FieldInfo* fi, const string& key, const JVal& v){
        fi->presentCount++;
        switch(v.kind){
            case JVal::Null:   fi->primitiveTypes.insert("null"); break;
            case JVal::Bool:   fi->primitiveTypes.insert("boolean"); break;
            case JVal::Num:    fi->primitiveTypes.insert("number"); break;
            case JVal::Str:    fi->primitiveTypes.insert("string"); break;
            case JVal::Obj:
                if(!fi->objectNode){
                    fi->objectNode=newNode();
                    fi->hasObject=true;
                }
                mergeObj(fi->objectNode, v);
                break;
            case JVal::Arr:
                fi->hasArray=true;
                for(auto& elem: v.arr){
                    mergeArrElem(fi, key, elem);
                }
                break;
        }
    }

    void mergeArrElem(FieldInfo* fi, const string& key, const JVal& v){
        switch(v.kind){
            case JVal::Null:   fi->arrayElemPrimitives.insert("null"); break;
            case JVal::Bool:   fi->arrayElemPrimitives.insert("boolean"); break;
            case JVal::Num:    fi->arrayElemPrimitives.insert("number"); break;
            case JVal::Str:    fi->arrayElemPrimitives.insert("string"); break;
            case JVal::Obj:
                fi->arrayHasObjects=true;
                if(!fi->arrayObjNode) fi->arrayObjNode=newNode();
                mergeObj(fi->arrayObjNode, v);
                break;
            case JVal::Arr:
                // spec: array elements are never arrays
                break;
        }
    }

    // After merging all data, compute optional flags properly.
    // optional = present in fewer objects than node->totalObjects
    void fixOptional(InterfaceNode* node){
        for(auto& [k,fi]: node->fields){
            if(fi->presentCount < node->totalObjects) fi->optional=true;
            // recurse
            if(fi->objectNode) fixOptional(fi->objectNode);
            if(fi->arrayObjNode) fixOptional(fi->arrayObjNode);
        }
    }

    // DFS to assign names: depth-first, alphabetical key order
    // Returns the InterfaceRecord for this node (may already exist)
    InterfaceRecord* assignName(InterfaceNode* node, const string& baseName){
        // Check if already assigned
        if(nodeToRecord.count(node)) return nodeToRecord[node];

        // Find a unique final name
        string finalName = baseName;
        if(usedNames.count(finalName)){
            int suffix=2;
            while(usedNames.count(baseName+to_string(suffix))) suffix++;
            finalName=baseName+to_string(suffix);
        }
        usedNames.insert(finalName);

        auto* rec = new InterfaceRecord{baseName, finalName, node};
        recordPool.push_back(unique_ptr<InterfaceRecord>(rec));
        nodeToRecord[node]=rec;
        allRecords.push_back(rec);

        // DFS into children in alphabetical key order
        for(auto& [k, fi]: node->fields){
            string childBase = string(1,(char)toupper((unsigned char)k[0])) + k.substr(1);
            if(fi->objectNode) assignName(fi->objectNode, childBase);
            if(fi->arrayObjNode) assignName(fi->arrayObjNode, childBase);
        }
        return rec;
    }

    // Build type string for a field
    string fieldType(FieldInfo* fi){
        // collect all type strings
        set<string> parts;

        for(auto& p: fi->primitiveTypes) parts.insert(p);

        if(fi->hasObject){
            auto* rec=nodeToRecord[fi->objectNode];
            parts.insert(rec->finalName);
        }

        if(fi->hasArray){
            // compute array element type string
            set<string> elemParts;
            for(auto& p: fi->arrayElemPrimitives) elemParts.insert(p);
            if(fi->arrayHasObjects){
                auto* rec=nodeToRecord[fi->arrayObjNode];
                elemParts.insert(rec->finalName);
            }

            string arrType;
            if(elemParts.empty()){
                arrType="unknown[]";
            } else {
                vector<string> ep(elemParts.begin(), elemParts.end());
                sort(ep.begin(),ep.end());
                if(ep.size()==1){
                    arrType=ep[0]+"[]";
                } else {
                    string u;
                    for(int i=0;i<(int)ep.size();i++){if(i)u+=" | ";u+=ep[i];}
                    arrType="("+u+")[]";
                }
            }
            parts.insert(arrType);
        }

        vector<string> pv(parts.begin(), parts.end());
        sort(pv.begin(), pv.end());
        string result;
        for(int i=0;i<(int)pv.size();i++){if(i) result+=" | "; result+=pv[i];}
        return result;
    }

    string buildOutput(){
        // Sort records by finalName (ASCII order)
        vector<InterfaceRecord*> sorted = allRecords;
        sort(sorted.begin(), sorted.end(), [](InterfaceRecord* a, InterfaceRecord* b){
            return a->finalName < b->finalName;
        });

        string out;
        for(int i=0;i<(int)sorted.size();i++){
            if(i) out+="\n\n";
            auto* rec=sorted[i];
            InterfaceNode* node=rec->node;
            if(node->fields.empty()){
                out+="export interface "+rec->finalName+" {}";
            } else {
                out+="export interface "+rec->finalName+" {\n";
                // fields in ASCII sorted order (map is already sorted)
                for(auto& [k,fi]: node->fields){
                    string opt = fi->optional ? "?" : "";
                    string type = fieldType(fi);
                    out+="  "+k+opt+": "+type+";\n";
                }
                out+="}";
            }
        }
        return out;
    }
};

static string solve(const string& rootName, const string& jsonText){
    size_t i=0;
    JVal root=parseVal(jsonText, i);

    Builder b;
    b.rootName=rootName;
    b.usedNames.insert(rootName);

    InterfaceNode* rootNode=b.newNode();
    b.root=rootNode;

    // Register root node first with its name
    auto* rootRec=new InterfaceRecord{rootName, rootName, rootNode};
    b.recordPool.push_back(unique_ptr<InterfaceRecord>(rootRec));
    b.nodeToRecord[rootNode]=rootRec;
    b.allRecords.push_back(rootRec);

    // Merge all top-level objects
    for(auto& elem: root.arr){
        if(elem.kind==JVal::Obj){
            b.mergeObj(rootNode, elem);
        }
    }

    // Fix optional: after all merges
    b.fixOptional(rootNode);

    // Assign names to child interfaces via DFS (root already assigned)
    // We do DFS manually from root in alphabetical key order
    // (re-use assignName but root already in nodeToRecord so it won't re-register)
    // We just need to walk children
    function<void(InterfaceNode*)> dfsAssign = [&](InterfaceNode* node){
        for(auto& [k,fi]: node->fields){
            string childBase = string(1,(char)toupper((unsigned char)k[0])) + k.substr(1);
            if(fi->objectNode && !b.nodeToRecord.count(fi->objectNode)){
                b.assignName(fi->objectNode, childBase);
            } else if(fi->objectNode){
                // already named, but still need to recurse into its children if not done
                dfsAssign(fi->objectNode);
            }
            if(fi->arrayObjNode && !b.nodeToRecord.count(fi->arrayObjNode)){
                b.assignName(fi->arrayObjNode, childBase);
            } else if(fi->arrayObjNode){
                dfsAssign(fi->arrayObjNode);
            }
        }
    };
    // We need to make sure root's children are assigned in DFS order
    // assignName already does DFS, but root was pre-registered.
    // So we call dfsAssign on root to handle children.
    dfsAssign(rootNode);

    return b.buildOutput();
}

int main(){
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int t;
    cin>>t;
    cin.ignore();

    string out;
    for(int i=0;i<t;i++){
        string rootName, jsonText;
        getline(cin, rootName);
        getline(cin, jsonText);
        if(i>0) out+="\n---\n";
        out+=solve(rootName, jsonText);
    }
    out+='\n';
    cout << out;
    return 0;
}