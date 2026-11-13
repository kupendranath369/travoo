import test_iter15_lgd_local_hire as t
db=t._db()
B,R,T="HIR-8288A5DC","LHR-5A5640FE","TKT-268A48"
print(db.tickets.delete_one({"ticket_id":T}).deleted_count,
      db.hires.delete_one({"booking_id":B,"passenger_id":"user_c8f97e2541c1"}).deleted_count,
      db.hire_requests.delete_one({"request_id":R,"passenger_id":"user_c8f97e2541c1"}).deleted_count,
      db.hire_dispatches.delete_many({"request_id":R}).deleted_count,
      db.notifications.delete_many({"ref":{"$in":[B,R]}}).deleted_count)
