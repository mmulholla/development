Feature: Chart submission with errors
  Partners or redhat associates submit charts which result in errors

  Examples:
  | vendor-tyoe  | vendor   | chart   | version  |
  | partners     | partners | vault   | 0.16.1   |
  | partners     | redhat   | jenkins | 1.0.0    |

  Scenario Outline: An unauthorized user submits a chart with report
    Given A <user> wants to submit a chart
    Given <vendor> of <vendor_type> <chart> and <version> of the chart
    And the user creates a branch to add a new chart version
    When the user sends a pull request with chart and report
    Then the pull request is not merged
    And user gets the <message> with steps to follow for resolving the issue in the pull request

    Examples:
      | message                                          | user         |
      | is not allowed to submit the chart on behalf of  | unauthorized |

  Scenario Outline: An authorized user submits a chart with incorrect version
    Given A <user> wants to submit a chart
    Given <vendor> of <vendor_type> <chart> and <version> of the chart
    Given Chart.yaml specifies a <badVersion>
    And the user creates a branch to add a new chart version
    When the user sends a pull request with chart and report
    Then the pull request is not merged
    And user gets the <message> with steps to follow for resolving the issue in the pull request

    Examples:
      | message                          | badVersion | user |
      | the chart version does not match | 9.9.9      | openshift-helm-charts-bot |


  Scenario Outline: An authorized user submits a chart with an invalid report
    Given A <user> wants to submit a chart
    Given <vendor> of <vendor_type> <version> is not present in the OWNERS file of the chart
    Given The report contains a failure
    And the user creates a branch to add a new chart version
    When the user sends a pull request with chart and report
    Then the pull request is not merged
    And user gets the <message> with steps to follow for resolving the issue in the pull request

    Examples:
      | message                          | user |
      | the chart version does not match | openshift-helm-charts-bot |

  Scenario Outline: An authorized user submits a chart which contains non-chart files
    Given A <user> wants to submit a chart
    Given <vendor> of <vendor_type> <version> is not present in the OWNERS file of the chart
    Given PR includes and <non-chart-file>
    And the user creates a branch to add a new chart version
    When the user sends a pull request with chart and report
    Then the pull request is not merged
    And user gets the <message> with steps to follow for resolving the issue in the pull request

    Examples:
      | message                     | non-chart-file | user |
      | pr includes nion chart file | OWNERS         | openshift-helm-charts-bot |

  Scenario Outline: An authorized user submits a chart which bad sha value
    Given A <user> wants to submit a chart
    Given <vendor> of <vendor_type> <version> is not present in the OWNERS file of the chart
    Given The sha value in the report does not match the chart sha
    And the user creates a branch to add a new chart version
    When the user sends a pull request with chart and report
    Then the pull request is not merged
    And user gets the <message> with steps to follow for resolving the issue in the pull request

    Examples:
      | message                |  user |
      | sha values don't match | openshift-helm-charts-bot |
