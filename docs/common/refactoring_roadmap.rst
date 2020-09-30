* Unify the format of the namespacing for TargetLists and ObservationGroups

    * At present, the "names" in the urlconf entries for TargetLists are of the format <action>-group. 
      The corresponding "names" in the urlconf entries for ObservationGroups are of the format group-<action>. 
      We should standardize. Also, the TargetGroupingListView urlconf entry is "targetgrouping", which should also 
      be fixed.

* Rename TargetLists to TargetGroups

    * The model name for the many-to-many relationship of targets is TargetList--however, this name is 
      avoided in documentation and displays due to the existence of the TargetListView, which lists all 
      targets. We should rename it to TargetGroups and ensure all related methods and references are up 
      to date.

* Rename TargetName to Alias

    * TargetName is the model name for name objects that are related to a target. However, because the
      target also has a "name" property, we should rename the model to "Alias". Confer with Rachel/Curtis 
      first.

* Update TextFields used for JSON to be actual JSONFields. This will require a migration script.

    * When first written, Django only supported JSONField for PostgreSQL DB backends. As of 3.1, JSONField 
      is standard, and should replace TextField where it can.
