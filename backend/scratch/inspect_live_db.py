from dotenv import dotenv_values
from pymongo import MongoClient
import certifi

vals = dotenv_values('backend/.env')
client = MongoClient(vals.get('MONGO_URI'), serverSelectionTimeoutMS=6000, tlsCAFile=certifi.where())
db = client['SenderX_db']

templates_col = db['templates']
versions_col = db['template_versions']

total_templates = templates_col.count_documents({})
active_count = templates_col.count_documents({'status': 'ACTIVE'})
draft_count = templates_col.count_documents({'status': 'DRAFT'})
deleted_count = templates_col.count_documents({'status': 'DELETED'})
soft_deleted_flag = templates_col.count_documents({'is_deleted': True})
missing_name_lower = templates_col.count_documents({'name_lower': {'$exists': False}})
null_name_lower = templates_col.count_documents({'name_lower': None})

print(f"Total templates: {total_templates}")
print(f"Active: {active_count}, Draft: {draft_count}, Deleted: {deleted_count}, is_deleted: {soft_deleted_flag}")
print(f"Missing name_lower: {missing_name_lower}, Null name_lower: {null_name_lower}")

# Check indexes
indexes = list(templates_col.list_indexes())
print("\nCurrent Templates Indexes:")
for idx in indexes:
    print(f" - {idx['name']}: {idx['key']} | unique={idx.get('unique', False)} | partial={idx.get('partialFilterExpression')}")

# Check versions
total_versions = versions_col.count_documents({})
print(f"\nTotal template versions: {total_versions}")
ver_indexes = list(versions_col.list_indexes())
print("Current Template Versions Indexes:")
for idx in ver_indexes:
    print(f" - {idx['name']}: {idx['key']} | unique={idx.get('unique', False)}")

# Check duplicates by (organization_id, name_lower) among ACTIVE / DRAFT
pipeline = [
    {'$match': {'status': {'$in': ['ACTIVE', 'DRAFT']}}},
    {'$group': {'_id': {'org': '$organization_id', 'nl': '$name_lower'}, 'count': {'$sum': 1}, 'docs': {'$push': {'id': '$template_id', 'name': '$name'}}}},
    {'$match': {'count': {'$gt': 1}}}
]
dups = list(templates_col.aggregate(pipeline))
print(f"\nDuplicates among ACTIVE/DRAFT: {len(dups)}")
for d in dups:
    print('DUP:', d)

# Inspect existing docs
docs = list(templates_col.find({}, {'_id': 0, 'template_id': 1, 'name': 1, 'name_lower': 1, 'status': 1, 'organization_id': 1, 'version': 1, 'created_at': 1}))
print(f"\nSample templates ({len(docs)}):")
for doc in docs:
    print(' ', doc)
