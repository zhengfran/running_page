# Running History

This context describes the personal activity history presented by the running page and how its records relate across data providers.

## Language

**Activity**:
A recorded exercise session that appears in the running history, such as a run, swim, walk, or workout.
_Avoid_: Run, when referring to all exercise types

**Run**:
An Activity classified as running. After the Source Cutover, only Runs enter the running history; non-running Legacy Activities remain part of the retained history.
_Avoid_: Activity, when the running-only distinction matters

**Activity Source**:
The provider from which an Activity enters the running history.
_Avoid_: App, backend

**Source Activity ID**:
The identifier assigned to an Activity by its Activity Source. It is meaningful only together with that source.
_Avoid_: Run ID, global activity ID

**Source Cutover**:
The point after which new Activities come from a different Activity Source while earlier Activities retain their existing source and identity.
_Avoid_: Migration, when historical Activities are not being replaced

**Cutover Boundary**:
The instant separating Legacy Activities from Activities owned by the new Activity Source. An Activity belongs to exactly one side according to when it started.
_Avoid_: Migration date, sync date

**Legacy Activity**:
An Activity retained from the Activity Source used before the Source Cutover.
_Avoid_: Old run, migrated Activity

**Source Archive**:
The private collection of original exports for Activities, preserved independently of the normalized Activities published by the running page.
_Avoid_: Cache, temporary download

**Public Route**:
The redacted route geometry published for an Activity. It is derived from, but deliberately less precise than, the route retained in the Source Archive.
_Avoid_: Raw route, source track

**Publication**:
Admission of a normalized Activity into the public running history. Publication occurs only after the Activity's original export is safely retained in the Source Archive.
_Avoid_: Sync, download

**Correction**:
An explicit, reviewable replacement of a published Activity or its Source Archive entry. A provider-side edit or deletion is not itself a Correction.
_Avoid_: Resync, automatic update
