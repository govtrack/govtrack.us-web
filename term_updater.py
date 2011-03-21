#!.env/bin/python
# -*- coding: utf-8 -*-
from common.system import setup_django
setup_django(__file__)
import re
from lxml.html import fromstring

from bill.models import BillTerm, TermType

TERMS = """
<p><strong>Agriculture and Food</strong><br>
  Agricultural conservation and pollution<br>
  Agricultural education<br>
  Agricultural insurance<br>
  Agricultural marketing and promotion<br>
  Agricultural pests<br>
  Agricultural practices and innovations<br>
  Agricultural prices, subsidies, credit<br>
  Agricultural research<br>
  Agricultural trade<br>
  Animal and plant health<br>
  Aquaculture<br>
  Farmland<br>
  Food industry and services<br>
  Food assistance and relief<br>
  Food supply, safety, and labeling<br>
  Fruit and vegetables<br>
  General agriculture matters<br>
  Grain<br>
  Horticulture and plants<br>
  Meat<br>
  Seafood</p>
<p><strong>Animals</strong><br> Animal protection and human-animal 
relationships<br> Birds<br> Endangered and threatened species<br> Fishes<br> Livestock<br> 
Mammals<br> Reptiles<br> Veterinary medicine and animal diseases<br> Wildlife 
conservation and habitat protection</p>
<p><strong>Armed Forces and National Security</strong><br>
  Alliances<br>
  Defense spending<br>
  Intelligence activities, surveillance, classified information<br>
  Military assistance and sales, agreements, alliances<br>
  Military cemeteries and funerals<br>
  Military civil functions<br>
  Military command and structure<br>
  <i>Military education and training (added 12/7/2009)</i><br>
  Military facilities and property<br>
  Military history<br>
  Military law<br>
  Military medicine<br>
  Military operations and strategy<br>
  Military personnel and dependents<br>
  Military procurement, research, weapons development<br>
  Military readiness<br>
  National Guard and reserves<br>
  Nuclear weapons<br>
  Strategic materials and reserves<br>
  Subversive activities<br>
  Veterans' medical care<br>
  Veterans' education, employment, rehabilitation<br>
  Veterans' loans, housing, homeless programs<br>
  <i>Veterans' organizations and recognition (added 12/7/2009)</i><br>
  Veterans' pensions and compensation<br>
  War and emergency powers</p>
<p><strong>Arts, Culture, 
Religion</strong><br> Art, artists, authorship<br> Books and print media<br> Cultural 
exchanges and relations<br> Digital media<br> Historical and cultural resources<br> 
Humanities programs funding<br> Language and bilingual programs<br> Libraries 
and archives<br> Literature<br> Museums, exhibitions, cultural centers<br> Music<br> 
Performing arts<br> Religion<br> Sound recording<br> Television and film</p><p><strong>Civil 
Rights and Liberties, Minority Issues</strong><br> Abortion<br> Age discrimination<br> 
Detention of persons<br> Disability and health-based discrimination<br> Due process 
and equal protection<br> Employment discrimination<br> Ethnic studies<br> First 
Amendment rights<br> Freedom of information<br> Pornography<br> Property rights<br> 
Protest and dissent<br> Racial and ethnic relations<br> Right of privacy<br> Sex, 
gender, sexual orientation discrimination<br> Voting rights<br>
Women's rights</p>
<p><strong>Commerce</strong><br>
  <i>Building construction (added 12/7/2009)</i><br>
  Business ethics<br>
  Business investment and capital<br>
  Business records<br>
  Competition and antitrust<br>
  Consumer affairs<br>
  Corporate finance and management<br>
  Gambling<br>
  General business and commerce matters<br>
  Industrial facilities<br>
  Industrial policy and productivity<br>
  Intellectual property<br>
  Manufacturing<br>
  Marketing and advertising<br>
  Minority and disadvantaged businesses<br>
  Product development and innovation<br>
  Product safety and quality<br>
  Retail and wholesale trades<br>
  Small business<br>
  Trade secrets and economic espionage<br>
  Women in business</p>
<p><strong>Congress</strong><br> 
Congressional agencies<br> Congressional committees<br> Congressional elections<br> 
Congressional leadership<br> Congressional officers and employees<br> Congressional 
operations and organization<br> Congressional oversight<br> House of Representatives<br> 
Legislative rules and procedure<br> Members of Congress<br> Senate<br> U.S. Capitol</p>
<p><strong>Crime and Law Enforcement</strong><br>
  Assault and harassment offenses<br>
  Computer crimes and identity theft<br>
  Correctional facilities and imprisonment<br>
  Crime prevention<br>
  Crime victims<br>
  Crimes against animals and natural resources<br>
  Crimes against children<br>
  Crimes against property<br>
  Crimes against women<br>
  Criminal investigation, prosecution, interrogation<br>
  Criminal justice information and records<br>
  Criminal procedure and sentencing<br>
  Drug trafficking and controlled substances<br>
  Firearms and explosives<br>
  <i>Fraud offenses and financial crimes (changed 12/7/2009)</i><br>
  Hate crimes<br>
  Juvenile crime and gang violence<br>
  Law enforcement administration and funding<br>
  Law enforcement officers<br>
  Organized crime<br>
  Sex offenses<br>
  Smuggling and trafficking<br>
  Terrorism<br>
  Violent crime<br>
  White-collar crime</p>
<p><strong>Economics 
and Public Finance</strong><br> Appropriations<br> Budget deficits and national 
debt<br> Budget process<br> Economic development<br> Economic performance and 
conditions<br> Economic theory <br>
  Government lending and loan guarantees<br> 
Government trust funds<br> 
Inflation and prices<br>
 Monetary policy<br> State and local finance<br> User charges 
and fees</p>
<p><strong>Education</strong><br> Academic performance and assessments<br> 
Adult education and literacy<br> Area studies and international education<br> 
Education of the disadvantaged<br> Education programs funding<br> Educational 
facilities and institutions<br> Educational technology and distance education<br> 
Elementary and secondary education<br> Foreign language<br> General education 
matters<br> Higher education<br>
Literacy and language arts<br> Minority education<br> Preschool education
<br>
School administration<br> 
Special education<br> Student aid and college costs 
<br> Teaching, teachers, curricula<br> Vocational education<br> Women's education</p>
<p><strong>Emergency 
Management</strong><br> Accidents<br> Civil disturbances<br> Disaster relief and 
insurance<br> Emergency communications systems<br> Emergency planning and evacuation<br> 
Fires<br> Homeland security<br> Natural disasters</p><p><strong>Energy</strong><br> 
Alternative and renewable resources<br> Coal<br> Electric power generation and 
transmission<br> Energy assistance for the poor and aged<br> Energy efficiency 
and conservation<br> Energy prices<br> Energy research<br> Energy revenues and 
royalties<br> Energy storage, supplies, demand<br> General energy matters <br> 
Hybrid, electric, and advanced technology vehicles<br> Lighting and heating<br> 
Motor fuels<br> Nuclear power<br> Oil and gas<br> Public utilities and utility 
rates</p><p><strong>Environmental Protection</strong><br> Air quality<br> Climate 
change
<br> 
Ecology<br> Environmental assessment, 
monitoring, research<br> Environmental regulatory procedures<br>
Environmental technology<br> 
Hazardous wastes 
and toxic substances<br>
Marine pollution <br> 
Noise pollution<br> Pollution liability<br> Radioactive 
wastes and releases<br> Soil pollution<br> Solid waste and recycling<br> Water 
quality</p>
<p><strong>Families</strong><br> Adoption and foster care<br> Adult 
day care<br> 
Child care and development<br>
 Child safety and welfare<br> Domestic violence and 
child abuse
<br>
 Family relationships<br> 
Marriage and family status<br> Separation, divorce, custody, support<br> Teenage 
pregnancy</p>
<p><strong>Finance and Financial Sector</strong><br>
  Accounting and auditing <br>
  Bank accounts, deposits, capital<br>
  Banking and financial institutions regulation<br>
  Bankruptcy<br>
  Commodities markets<br>
  Consumer credit<br>
  Credit and credit markets<br>
  Currency <br>
  Financial crises and stabilization<br>
  Financial literacy<br>
  Financial services and investments<br>
  Insurance industry and regulation<br>
  Interest, dividends, interest rates<br>
  Life, casualty, property insurance<br>
  Real estate business<br>
  Securities</p>
<p><strong>Foreign Trade and International Finance</strong><br> 
Buy American requirements<br> Competitiveness, trade promotion, trade deficits<br> 
Foreign and international corporations<br> Foreign loans and debt<br> Free trade 
and trade barriers<br> Foreign and international banking<br> International monetary 
system and foreign exchange<br> Normal trade relations, most-favored-nation treatment<br> 
Tariffs<br> Trade adjustment assistance<br> Trade agreements and negotiations<br> 
Trade restrictions<br> U.S. and foreign investments</p><p><strong>Government Operations 
and Politics</strong><br> Administrative law and regulatory procedures<br>Advisory 
bodies<br>Census and government statistics
<br>
Commemorative events and holidays<br> 
Community life and organization<br> Congressional-executive 
branch relations<br>
Congressional tributes<br>
  District of Columbia affairs<br>
  Elections, 
  voting, political campaign regulation<br>
  Executive agency funding and structure<br>
  Federal officials<br>
  Federal preemption<br>
  Federally chartered organizations<br>
  Government buildings, 
  facilities, and property<br>
  Government corporations and government-sponsored 
  enterprises<br>
  Government employee pay, benefits, personnel management<br>
  Government 
  ethics and transparency, public corruption<br>
  Government information and archives<br>
  Government investigations<br>
  Government liability
  <br>
  Intergovernmental 
  relations<br>
  Licensing and registrations<br>
  National symbols<br>
  Performance measurement<br>
  Political movements and philosophies<br>
  Political parties 
  and affiliation <br>
  Political representation<br>
  Postal service<br>
  Presidents 
  and presidential powers<br>
  Public-private cooperation<br>
  Public contracts and procurement<br>
  Public participation 
  and lobbying<br>
  State and local government operations<br>
  U.S. territories and 
  protectorates</p>
<p><strong>Health</strong><br>
  Aging<br>
  Allergies<br>
  Allied health services<br>
  Alternative treatments <br>
  Birth defects<br>
  Blood and blood diseases<br>
  Cancer<br>
  Cardiovascular and respiratory health<br>
  Cell biology and embryology<br>
  Child health<br>
  Comprehensive health care <br>
  Dental care<br>
  Digestive and metabolic diseases<br>
  Disability and paralysis<br>
  Drug, alcohol, tobacco use<br>
  Drug and radiation therapy<br>
  Drug safety, medical device, and laboratory regulation <br>
  Emergency medical services and trauma care<br>
  Environmental health<br>
  Family planning and birth control<br>
  General health and health care finance matters<br>
  Genetics <br>
  Health care costs and insurance<br>
  Health care quality <br>
  Health care coverage and access<br>
  Health facilities and institutions<br>
  Health information and medical records<br>
  Health personnel <br>
  Health programs administration and funding<br>
  Health promotion and preventive care<br>
  Health technology, devices, supplies<br>
  Hearing, speech, and vision care<br>
  Hereditary and development disorders<br>
  HIV/AIDS<br>
  Home and outpatient care<br>
  Hospital care<br>
  Immunology<br>
  Infectious and parasitic diseases<br>
  Long-term, rehabilitative, and terminal care<br>
  Medicaid<br>
  Medical education<br>
  Medical ethics<br>
  Medical research<br>
  Medical tests and diagnostic methods<br>
  Medicare<br>
  Mental health<br>
  Minority health<br>
  Musculoskeletal and skin diseases<br>
  Neurological disorders<br>
  Nursing<br>
  Nutrition and diet<br>
  Organ and tissue donation and transplantation<br>
  Physical fitness and lifestyle<br>
  Prescription drugs<br>
  Radiobiology <br>
  Sex and reproductive health<br>
  Sexually transmitted diseases<br>
  Surgery and anesthesia<br>
  Women's health<br>
  World health</p>
<p><strong>Housing 
and Community Development</strong><br> Cooperative and condominium housing<br> 
Homelessness and emergency shelter<br> Housing and community development funding<br> 
Housing finance and home ownership<br> Housing for the elderly and disabled<br>
  <i>Housing industry and standards (changed 12/7/2009)</i><br>
   Housing supply and affordability<br> 
Low- and moderate-income housing<br> Public housing<br> Residential rehabilitation 
and home repair<br> Rural conditions and development<br> Small towns<br> Urban 
and suburban affairs and development</p><p><strong>Immigration</strong><br> Border 
security and unlawful immigration<br> Citizenship and naturalization<br> Foreign 
labor<br> Human trafficking<br> Immigrant health and welfare<br> Immigration status 
and procedures<br> Refugees, asylum, displaced persons<br> Visas and passports</p><p><strong>International 
Affairs</strong><br> Arab-Israeli relations<br> Arms control and nonproliferation<br> 
Collective security<br> Conflicts and wars<br> Diplomacy, foreign officials, Americans 
abroad<br> Foreign aid and international relief<br> General foreign operations 
matters<br> Human rights<br> International exchange and broadcasting<br> International 
finance and foreign exchange<br> International law and treaties<br> International 
organizations and cooperation<br> Militias and paramilitary groups<br> Multilateral 
development programs<br> Reconstruction and stabilization<br> Rule of law and 
government transparency<br> Sanctions<br> Sovereignty, recognition, national governance 
and status<br>
War crimes, genocide, crimes against humanity</p>
<p><strong>Labor and Employment</strong><br>
  Employee benefits and pensions<br>
  Employment and training programs<br>
  Employment discrimination and employee rights<br>
  Employee leave<br>
  Labor standards<br>
  Labor-management relations<br>
  Migrant, seasonal, agricultural labor<br>
  Personnel records<br>
  Self-employed<br>
  <i>Temporary and part-time employment (added 12/7/2009)<br>
  </i>Unemployment<br>
  Wages and earnings<br>
  Women's employment<br>
  Worker safety and health<br>
  Youth employment and child labor</p>
<p><strong>Law</strong><br> 
Administrative remedies<br>
Alternative dispute resolution, mediation, arbitration<br> 
Civil actions and liability
<br>
 Constitution and constitutional 
amendments<br> Contracts and agency<br> Judicial procedure and administration<br> 
Evidence and witnesses<br> Federal appellate courts<br> Federal district courts<br>
Judges<br> 
Judicial review and appeals<br> Jurisdiction and venue<br> Lawyers and legal services<br>
  Legal fees and court costs<br> 
Specialized courts<br> State and local courts<br> Supreme Court</p>
<p><strong>Native 
Americans</strong><br> Alaska Natives and Hawaiians<br> Federal-Indian relations<br> 
General Native American affairs matters<br> Indian claims<br> Indian lands and 
resources rights<br> Indian social and development programs</p>
<p><strong>Private Legislation</strong></p>
<p><strong>Public 
Lands and Natural Resources</strong><br> Earth sciences and observation<br> Forests<br> 
General public lands matters<br> Historic sites and heritage areas<br> Land transfers<br> 
Land use and conservation<br> Marine and coastal resources, fisheries<br> Metals<br> 
Mining<br> Monuments and memorials<br> Parks, recreation areas, trails<br> Polar 
regions<br> Seashores and lakeshores<br> Wilderness and natural areas, wildlife 
refuges, wild rivers, habitats</p><p><strong>Science, Technology, Communications</strong><br> 
Advanced technology and technological innovations<br> Astronomy<br> Atmospheric 
science and weather<br>
  Broadcasting, cable, digital technologies<br> 
 Computers and information 
technology<br> General science and technology matters<br> International scientific 
cooperation<br> Internet and video services<br>
  News media and reporting<br>
 Photography and imaging<br> Political 
advertising<br> Research administration and funding<br> Research and development<br> 
Research ethics<br> Science and engineering education<br> Spacecraft and satellites<br> 
Space flight and exploration<br>
  Technology assessment<br>
 Technology transfer and commercialization<br> 
Telecommunication rates and fees<br> Telephone and wireless communication<br> 
Time and calendar</p><p><strong>Social Sciences and History</strong><br> Archaeology 
and anthropology<br> Behavioral sciences<br>
Military history<br> Policy sciences
<br> 
Presidential administrations<br> U.S. history<br> World history</p>
<p><strong>Social 
Welfare</strong><br> Disability assistance<br> National and community service<br> 
Poverty and welfare assistance<br> Social security and elderly assistance<br> 
Social work, volunteer service, charitable organizations</p><p><strong>Sports 
and Recreation</strong><br> Athletes<br> Games and hobbies<br> Olympic games<br> 
Outdoor recreation<br> Professional sports<br> School athletics<br> Sports and 
recreation facilities</p><p><strong>Taxation</strong><br> 
  Capital gains tax<br>
  Employment taxes<br>
  General 
taxation matters<br>Income tax credits<br> Income tax deductions<br> Income tax 
deferral<br> Income tax exclusion<br> Income tax rates<br> Sales and excise taxes<br> 
State and local taxation<br> Tax administration and collection, taxpayers<br> 
Tax reform and tax simplification<br>
Tax treatment of families<br> 
Tax-exempt organizations<br> Taxation of 
foreign income<br> Transfer and inheritance taxes</p>
<p><strong>Transportation 
and Public Works</strong><br> Aviation and airports<br> Coast guard<br>
Commuting<br> 
Infrastructure 
development<br> Marine and inland water transportation<br> Motor carriers<br> 
Motor vehicles<br> Navigation, waterways, harbors<br> Pedestrians and bicycling<br> 
Pipelines<br> Public transit<br> Railroads<br> Roads and highways<br>
Transportation costs<br> 
Transportation 
employees<br> Transportation programs funding<br> Transportation safety and security<br> 
Travel and tourism</p>
<p><strong>Water Resources Development</strong><br> Aquatic 
ecology<br> Dams and canals<br> Floods and storm protection<br> Hydrology and 
hydrography<br> Lakes and rivers
<br>
Water resources funding<br> 
Water storage<br> 
Water use and supply<br> Watersheds<br> Wetlands</p>
"""

GEO_TERMS = """
Administrative Conference of the U.S.
Afghanistan
Alabama
Alaska
Albania
American Battle Monuments Commission
American Samoa 
Andorra 
Anguilla 
Antigua and Barbuda 
Appalachian Regional Commission
Architect of the Capitol
Architectural and Transportation Barriers Compliance Board
Arctic Ocean 
Argentina 
Arizona 
Arkansas 
Armed Forces Retirement Home
Armenia 
Arms Control and Disarmament Agency
Army Corps of Engineers
ASEAN countries
Asia
Atlantic Coast (U.S.)
Atlantic Ocean 
Australia 
Austria 
Azerbaijan
Bahamas 
Bahrain 
Bangladesh 
Barbados 
Belgium 
Belize 
Bering Sea 
Bermuda 
Bhutan 
Bolivia 
Bosnia and Herzegovina 
Botswana 
Brazil 
Broadcasting Board of Governors
Brunei 
Burkina Faso 
Burma 
Burundi
California 
Cambodia 
Cameroon 
Canada 
Caribbean area
Caribbean Sea 
Cayman Islands 
Centers for Disease Control and Prevention (CDC)
Central African Republic 
Central America 
Central Intelligence Agency (CIA)
Chesapeake Bay 
Chile 
China 
Colombia 
Colorado 
Commission of Fine Arts
Commission on Civil Rights
Committee for Purchase from People Who Are Blind or Severely Disabled
Commodity Credit Corporation
Commodity Futures Trading Commission
Community Development Financial Institutions Fund
Comoros 
Congo 
Congress
Congressional Budget Office (CBO)
Congressional Research Service (CRS)
Connecticut 
Consumer Product Safety Commission
Corporation for National and Community Service
Costa Rica 
Croatia 
Cuba 
Cyprus 
Czech Republic
Defense Nuclear Facilities Safety Board
Delaware 
Delaware River Basin Commission
Democratic Republic of the Congo 
Department of  Agriculture
Department of  Commerce
Department of  Defense
Department of  Education
Department of  Energy
Department of  Health and Human Services
Department of  Homeland Security
Department of  Housing and Urban Development
Department of  Justice
Department of  Labor
Department of  State
Department of  the Interior
Department of  the Treasury
Department of  Transportation
Department of  Veterans Affairs
Diego Garcia
Director of National Intelligence
District of Columbia 
Dominica 
Dominican Republic 
Drug Enforcement Administration (DEA)
East Timor 
Ecuador 
Egypt 
El Salvador 
Election Assistance Commission
Environmental Protection Agency (EPA)
Equal Employment Opportunity Commission (EEOC)
Equatorial Guinea 
Eritrea 
Estonia 
Ethiopia 
Europe 
European Union
Everglades 
Executive Office of the President
Export-Import Bank of the United States
Farm Credit Administration
Federal Bureau of Investigation (FBI)
Federal Communications Commission (FCC)
Federal Crop Insurance Corporation
Federal Deposit Insurance Corporation (FDIC)
Federal Election Commission (FEC)
Federal Emergency Management Agency (FEMA)
Federal Energy Regulatory Commission (FERC)
Federal Home Loan Bank Board
Federal Housing Finance Board
Federal Labor Relations Authority
Federal Maritime Commission
Federal Mediation and Conciliation Service
Federal Mine Safety and Health Review Commission
Federal Prison Industries, Inc.
Federal Reserve System
Federal Retirement Thrift Investment Board
Federal Trade Commission (FTC)
Finland 
Florida 
Food and Drug Administration (FDA)
Gabon 
Gambia 
Gaza Strip
General Services Administration
Georgia 
Georgia (Republic)
Germany 
Ghana 
Government Accountability Office (GAO)
Government National Mortgage Association (Ginnie Mae)
Government Printing Office (GPO)
Great Lakes 
Great Plains 
Greece 
Greenland 
Grenada 
Guadeloupe 
Guam 
Guatemala 
Guinea 
Guinea-Bissau 
Gulf of Mexico 
Gulf States 
Guyana
Haiti 
Hawaii 
Honduras 
Hong Kong 
House Committee on Agriculture
House Committee on Appropriations
House Committee on Armed Services
House Committee on Education and Labor
House Committee on Energy and Commerce
House Committee on Financial Services
House Committee on Foreign Affairs
House Committee on Homeland Security
House Committee on House Administration
House Committee on Natural Resources
House Committee on Oversight and Government Reform
House Committee on Rules
House Committee on Science and Technology
House Committee on Small Business
House Committee on Standards of Official Conduct
House Committee on the Budget
House Committee on the Judiciary
House Committee on Transportation and Infrastructure
House Committee on Veterans’ Affairs
House Committee on Ways and Means
House of Representatives
House Permanent Select Committee on Intelligence
House Select Committee on Energy Independence and Global Warming
Iceland 
Idaho 
Illinois
India 
Indiana
Interagency Council on Homelessness
Inter-American Foundation
Internal Revenue Service (IRS)
Iowa 
Iran 
Iraq 
Ireland 
Israel 
Italy 
Ivory Coast
Jamaica 
Japan 
Japan-U.S. Friendship Commission
Joint Committee on Taxation
Joint Economic Committee
Jordan
Kansas 
Kazakhstan 
Kentucky 
Kenya 
Kiribati 
Kosovo
Kuwait 
Kyrgyzstan
Latin America 
Lebanon 
Legal Services Corporation
Lesotho 
Liberia 
Library of Congress
Libya 
Liechtenstein 
Lithuania 
Long Island Sound
Louisiana 
Luxembourg
Macau 
Macedonia 
Madagascar 
Maine 
Malawi 
Malaysia 
Maldives 
Mali 
Malta 
Marine Mammal Commission
Marshall Islands 
Martinique 
Maryland 
Massachusetts 
Mauritania 
Mauritius 
Medicare Payment Advisory Commission
Merit Systems Protection Board
Mexico 
Michigan 
Micronesia 
Middle East
Minnesota 
Mississippi 
Mississippi River 
Missouri 
Missouri River 
Moldova 
Mongolia 
Montana 
Montenegro 
Montserrat 
Morocco 
Mozambique
Namibia 
National Aeronautics and Space Administration
National Archives and Records Administration
National Capital Planning Commission
National Commission on Libraries and Information Science
National Council on Disability
National Credit Union Administration
National Foundation on the Arts and the Humanities
National Indian Gaming Commission
National Institutes of Health (NIH)
National Labor Relations Board (NLRB)
National Mediation Board
National Railroad Passenger Corporation (Amtrak)
National Science Foundation
National Transportation Safety Board (NTSB)
Nebraska 
Neighborhood Reinvestment Corporation
Nepal 
Netherlands 
Netherlands Antilles 
Nevada 
New Hampshire 
New Jersey 
New Mexico 
New York City 
New York State 
New Zealand 
Nicaragua 
Niger 
Nigeria 
North America 
North Carolina 
North Dakota 
North Korea 
Northern Ireland 
Northern Mariana Islands 
Norway 
Nuclear Regulatory Commission (NRC)
Nuclear Waste Technical Review Board
Occupational Safety and Health Review Commission
Oceania 
Office of Government Ethics
Office of Management and Budget (OMB)
Office of Personnel Management (OPM)
Office of Science and Technology Policy
Office of Special Counsel
Office of the U.S. Trade Representative
Ohio 
Oklahoma 
Oregon
Organization of American States
Overseas Private Investment Corporation (OPIC)
Pacific Ocean 
Pakistan 
Palau 
Palestinian Authority
Panama 
Panama Canal 
Papua New Guinea 
Paraguay 
Peace Corps
Pennsylvania 
Pension Benefit Guaranty Corporation
Persian Gulf 
Persian Gulf States
Peru 
Philippines 
Poland 
Portugal 
Postal Regulatory Commission
Puerto Rico 
Puget Sound
Rhode Island 
Romania 
Russia 
Rwanda
Saint Kitts and Nevis 
Saint Lawrence Seaway 
Saint Lucia 
Saint Vincent and the Grenadines 
Samoa 
San Marino 
Sao Tome and Principe 
Saudi Arabia 
Securities and Exchange Commission (SEC)
Selective Service System
Senate Committee on Agriculture, Nutrition, and Forestry
Senate Committee on Appropriations
Senate Committee on Armed Services
Senate Committee on Banking, Housing, and Urban Affairs
Senate Committee on Commerce, Science, and Transportation
Senate Committee on Energy and Natural Resources
Senate Committee on Environment and Public Works
Senate Committee on Finance
Senate Committee on Foreign Relations
Senate Committee on Health, Education, Labor, and Pensions
Senate Committee on Homeland Security and Governmental Affairs
Senate Committee on Indian Affairs
Senate Committee on Rules and Administration
Senate Committee on Small Business and Entrepreneurship
Senate Committee on the Budget
Senate Committee on the Judiciary
Senate Committee on Veterans’ Affairs
Senate Select Committee on Ethics
Senate Select Committee on Intelligence
Senate Special Committee on Aging
Sierra Leone 
Singapore 
Slovakia 
Slovenia 
Small Business Administration
Smithsonian Institution
Social Security Administration
Somalia 
South Africa 
South Asia 
South Carolina 
South Dakota 
South Korea 
Spain 
Sri Lanka 
Sudan 
Surface Transportation Board
Swaziland 
Sweden 
Switzerland 
Syria
Taiwan 
Tajikistan 
Tanzania 
Tennessee
Tennessee Valley Authority
Texas
Thailand 
Tibet 
Togo 
Tonga 
Trade and Development Agency
Trinidad and Tobago 
Tunisia 
Turkey 
Turkmenistan 
Turks and Caicos
Tuvalu
U.S. Agency for International Development (USAID)
U.S. Holocaust Memorial Council
U.S. Institute of Peace
U.S. International Trade Commission
U.S. Postal Service
U.S. Sentencing Commission
U.S.S.R.
Uganda 
Ukraine 
United Arab Emirates 
United Kingdom 
United Nations
Uruguay 
Utah 
Uzbekistan
Vanuatu 
Vatican City 
Venezuela 
Vermont 
Vietnam
Virginia
Washington State 
West Bank 
West Virginia 
Western Hemisphere 
Western Sahara 
Wisconsin 
Wyoming
Yemen
Zimbabwe
"""

def normalize_name(name):
    # Normalize spaces
    name = re.sub(r'[\n\r\s]+', ' ', name).strip()
    # Strip change time
    name = re.sub(r'\(.+\)$', '', name)
    # Strip leading and trailing spaces
    name = name.strip()
    return name


def parse():
    # Processing data from http://thomas.loc.gov/help/terms-subjects.html
    tree = fromstring(TERMS)
    for block in tree.xpath('./p'):
        parent_name = normalize_name(block.xpath('./strong')[0].text)
        try:
            parent_term = BillTerm.objects.get(name=parent_name, term_type=TermType.new, parent=None)
        except BillTerm.DoesNotExist:
            print 'Creating new Top Term: %s' % parent_name
            parent_term = BillTerm.objects.create(name=parent_name, term_type=TermType.new)

        for item in block.xpath('./br'):
            if item.tail:
                child_name = normalize_name(item.tail)
                try:
                    child_term = BillTerm.objects.get(name=child_name, term_type=TermType.new, parent=parent_term)
                except BillTerm.DoesNotExist:
                    print 'Creating new Child Term: %s / %s' % (parent_name, child_name)
                    child_term = BillTerm.objects.create(name=child_name, term_type=TermType.new, parent=parent_term)

        for item in block.xpath('./i'):
            child_name = normalize_name(item.text)
            try:
                child_term = BillTerm.objects.get(name=child_name, term_type=TermType.new, parent=parent_term)
            except BillTerm.DoesNotExist:
                print 'Creating new Child Term: %s / %s' % (parent_name, child_name)
                child_term = BillTerm.objects.create(name=child_name, term_type=TermType.new, parent=parent_term)


    # Processing data from http://thomas.loc.gov/help/terms-names.html
    parent_term = BillTerm.objects.get(name="Geographic Areas, Entities, and Committees", term_type=TermType.new, parent=None)
    for name in filter(None, (x.strip() for x in GEO_TERMS.splitlines())):
        try:
            child_term = BillTerm.objects.get(name=name, parent=parent_term, term_type=TermType.new)
        except BillTerm.DoesNotExist:
            print 'Creating new Child Term: %s / %s' % (parent_term.name, name)
            child_term = BillTerm.objects.create(name=name, term_type=TermType.new, parent=parent_term)


if __name__ == '__main__':
    parse()
